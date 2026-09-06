import { useState, useEffect, forwardRef } from 'react'
import { t } from '../lib/i18n.js'
import { MOBILE, isAndroid } from '../lib/mobile.js'
import { checkForUpdate, shouldShowUpdatePrompt, remindUpdateLater, downloadAndInstall } from '../lib/update.js'
import { useUI } from '../store/useUI.js'
import { useStore } from '../store/useStore.js'
import { Button } from './ui.jsx'

/**
 * Download progress sheet for native APK downloads.
 */
export const DownloadProgress = forwardRef(function DownloadProgress(_, ref) {
  const [pct, setPct] = useState(0)
  const [text, setText] = useState(t('Starting download…'))
  if (ref) ref(function update(received, total) {
    if (total > 0) {
      const p = Math.min(100, Math.round((received / total) * 100))
      setPct(p)
      setText(t('{0} %', p))
    } else {
      setText(t('{0} MB', (received / 1_000_000).toFixed(1)))
    }
  })
  return (
    <div style={{ textAlign: 'center', padding: '8px 0' }}>
      <h3>{t('Downloading update…')}</h3>
      <div style={{ margin: '16px 0', height: 6, borderRadius: 3, background: 'var(--fill-3)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: pct + '%', background: 'var(--acc)', borderRadius: 3, transition: 'width .2s' }} />
      </div>
      <div className="muted small">{text}</div>
    </div>
  )
})

/**
 * Initiates the update process: downloads APK on Android or opens release on web.
 */
export async function startAppUpdate(updateInfo) {
  const ui = useUI.getState()
  if (!updateInfo) return

  let onAndroid = false
  try { onAndroid = await isAndroid() } catch { /* ignore */ }

  if (MOBILE && onAndroid && updateInfo.apkUrl) {
    let closeProgress = null
    let setProgress = null
    ui.openSheet(close => {
      closeProgress = close
      return <DownloadProgress ref={fn => { setProgress = fn }} />
    }, { locked: true })

    try {
      let expectedHash = null
      if (updateInfo.hashUrl) {
        try {
          const hashRes = await fetch(updateInfo.hashUrl)
          if (hashRes.ok) expectedHash = (await hashRes.text()).split(/\s/)[0]
        } catch (e) { /* reported below */ }
      }
      if (!/^[0-9a-f]{64}$/i.test(expectedHash || '')) {
        throw new Error(t('Checksum not available — not installing'))
      }
      await downloadAndInstall(updateInfo.apkUrl, expectedHash, (received, total) => {
        if (setProgress) setProgress(received, total)
      })
      if (closeProgress) closeProgress()
    } catch (e) {
      if (closeProgress) closeProgress()
      ui.toast(t('Update failed: {0}', e.message))
    }
  } else {
    const targetUrl = updateInfo.releaseUrl || updateInfo.apkUrl || 'https://github.com/SmitroniX/SmiTriX/releases'
    window.open(targetUrl, '_blank', 'noopener')
  }
}

/**
 * Update prompt dialog offering "Update now" and "Remind me later".
 */
export function UpdatePromptDialog({ updateInfo, close }) {
  const onUpdateNow = () => {
    close()
    startAppUpdate(updateInfo)
  }

  const onRemindLater = () => {
    remindUpdateLater(updateInfo?.latestVersion)
    close()
  }

  const ver = updateInfo?.latestVersion || ''

  return (
    <div style={{ textAlign: 'center', padding: '8px 2px 2px' }}>
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
        <img
          src="icon-180.png"
          width="72"
          height="72"
          style={{ borderRadius: 16, boxShadow: '0 6px 20px rgba(0,0,0,0.45)' }}
          alt="SmiTriX"
        />
      </div>
      <h3 style={{ marginBottom: 6, fontSize: 20, fontWeight: 700 }}>{t('New release available!')}</h3>
      <div className="muted" style={{ marginBottom: 20, fontSize: 14, lineHeight: 1.5 }}>
        {t('SmiTriX v{0} is now available. Update now to get the latest features and improvements.', ver)}
      </div>
      <button className="btn primary" style={{ width: '100%', marginBottom: 8 }} onClick={onUpdateNow}>
        {t('Update now')}
      </button>
      <Button variant="ghost" className="dim" style={{ width: '100%' }} onClick={onRemindLater}>
        {t('Remind me later')}
      </Button>
    </div>
  )
}

/**
 * Opens the update prompt dialog.
 */
export function promptUpdate(updateInfo) {
  useUI.getState().openSheet(close => <UpdatePromptDialog updateInfo={updateInfo} close={close} />, { kind: 'center' })
}

/**
 * Automatic update checker component mounted in Shell.
 * Checks for updates on app boot after a brief delay and prompts if needed.
 */
export function UpdateChecker() {
  const ready = useStore(s => s.ready)

  useEffect(() => {
    if (!ready) return
    // Wait 2.5 seconds after app boot so startup finishes smoothly
    const timer = setTimeout(() => {
      checkForUpdate().then(info => {
        if (info?.hasUpdate && shouldShowUpdatePrompt(info)) {
          promptUpdate(info)
        }
      }).catch(() => {
        // Silent on network error
      })
    }, 2500)
    return () => clearTimeout(timer)
  }, [ready])

  return null
}
