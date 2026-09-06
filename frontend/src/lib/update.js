// Update check — compares the installed version (__APP_VERSION__) against
// the latest release tag on GitLab and optionally downloads + installs the APK.
//
// The GitLab releases API is public for this project, so no token is needed.
// On Android (Capacitor), the APK asset is downloaded to the cache directory
// and handed to the system installer via a content:// URI.

import { MOBILE } from './mobile.js'

const GITHUB_REPO = 'SmitroniX/SmiTriX'
const GITHUB_RELEASES_URL = `https://api.github.com/repos/${GITHUB_REPO}/releases?per_page=1`
const GITLAB_PROJECT_ID = 'jogdandasmit%2FSmiTriX'
const RELEASES_URL = `https://gitlab.com/api/v4/projects/${GITLAB_PROJECT_ID}/releases`

export const REMIND_STORAGE_KEY = 'smitrix_update_remind_later'
export const REMIND_DELAY_MS = 24 * 60 * 60 * 1000 // 24 hours

/**
 * Compares two semver strings (e.g. "1.2.11" vs "1.3.0").
 * Returns  1 if a > b, -1 if a < b, 0 if equal.
 */
export function compareSemver(a, b) {
  const pa = (a || '').replace(/^v/, '').split('.').map(Number)
  const pb = (b || '').replace(/^v/, '').split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    const diff = (pa[i] || 0) - (pb[i] || 0)
    if (diff > 0) return 1
    if (diff < 0) return -1
  }
  return 0
}

/**
 * Checks if the user should be prompted for an update, taking into account
 * whether they previously clicked "Remind me later" for this version within 24 hours.
 */
export function shouldShowUpdatePrompt(updateInfo) {
  if (!updateInfo || !updateInfo.hasUpdate || !updateInfo.latestVersion) return false
  try {
    const raw = localStorage.getItem(REMIND_STORAGE_KEY)
    if (raw) {
      const data = JSON.parse(raw)
      if (data && compareSemver(data.version || '', updateInfo.latestVersion) >= 0) {
        if (Date.now() - (data.timestamp || 0) < REMIND_DELAY_MS) {
          return false
        }
      }
    }
  } catch {
    // If reading localStorage fails, default to showing
  }
  return true
}

/**
 * Records that the user requested to be reminded later about this version.
 */
export function remindUpdateLater(version) {
  try {
    localStorage.setItem(REMIND_STORAGE_KEY, JSON.stringify({
      version: version || '',
      timestamp: Date.now()
    }))
  } catch {
    // ignore storage errors
  }
}

/**
 * Clears the stored reminder.
 */
export function clearUpdateReminder() {
  try {
    localStorage.removeItem(REMIND_STORAGE_KEY)
  } catch {
    // ignore
  }
}

/**
 * Checks the releases API for a newer version (GitHub first, fallback to GitLab).
 * Returns { hasUpdate, latestVersion, apkUrl, hashUrl, releaseNotes, releaseUrl } or throws on network failure.
 */
let cached = null
export function resetUpdateCheck() { cached = null }
export async function checkForUpdate() {
  if (!cached) cached = fetchLatest().catch(e => { cached = null; throw e })
  return cached
}
async function fetchLatest() {
  let release = null

  try {
    const ghRes = await fetch(GITHUB_RELEASES_URL, {
      headers: { Accept: 'application/vnd.github.v3+json' }
    })
    if (ghRes.ok) {
      const data = await ghRes.json()
      if (Array.isArray(data) && data.length > 0) {
        release = data[0]
      }
    }
  } catch {
    // GitHub fetch failed; fallback to GitLab below
  }

  if (!release) {
    const res = await fetch(RELEASES_URL + '?per_page=1')
    if (!res.ok) throw new Error(`GitLab API ${res.status}`)
    const releases = await res.json()
    if (!releases.length) return { hasUpdate: false, latestVersion: __APP_VERSION__, apkUrl: null, hashUrl: null, releaseNotes: '', releaseUrl: null }
    release = releases[0]
  }

  const latestVersion = (release.tag_name || '').replace(/^v/, '')
  const hasUpdate = compareSemver(latestVersion, __APP_VERSION__) > 0

  let apkUrl = null
  let hashUrl = null
  const releaseUrl = release.html_url || `https://github.com/SmitroniX/SmiTriX/releases/tag/v${latestVersion}`
  const releaseNotes = release.body || release.description || ''

  if (Array.isArray(release.assets)) {
    const apk = release.assets.find(a => /\.apk$/i.test(a?.name || '') || /\.apk$/i.test(a?.browser_download_url || '') || /\.apk$/i.test(a?.url || ''))
    if (apk) apkUrl = apk.browser_download_url || apk.url
    const hash = release.assets.find(a => /\.apk\.sha256$/i.test(a?.name || '') || /sha256/i.test(a?.name || '') || /\.apk\.sha256$/i.test(a?.browser_download_url || ''))
    if (hash) hashUrl = hash.browser_download_url || hash.url
  } else if (release.assets?.links?.length) {
    const apkLink = release.assets.links.find(l => /\.apk$/i.test(l?.url || '') || /\.apk$/i.test(l?.direct_asset_url || ''))
    if (apkLink) apkUrl = apkLink.direct_asset_url || apkLink.url
    const hashLink = release.assets.links.find(l => /\.apk\.sha256$/i.test(l?.url || '') || /\.apk\.sha256$/i.test(l?.direct_asset_url || '') || /sha256/i.test(l?.name || ''))
    if (hashLink) hashUrl = hashLink.direct_asset_url || hashLink.url
  }

  return { hasUpdate, latestVersion, apkUrl, hashUrl, releaseNotes, releaseUrl }
}

/**
 * Computes the SHA-256 hash of an ArrayBuffer using the Web Crypto API.
 * Returns the hex-encoded digest string.
 */
export async function sha256(buffer) {
  const hash = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Downloads the APK from `url`, verifies its SHA-256 hash against `expectedHash`
 * (if provided), and triggers the Android installer.
 * Only works on the MOBILE (Capacitor) build with Android.
 *
 * @param {string} url - Direct download URL for the APK
 * @param {string|null} expectedHash - Expected SHA-256 hex string (from .sha256 asset), or null to skip verification
 * @param {function|null} onProgress - Called with (received, total) bytes during download, or null
 */
export async function downloadAndInstall(url, expectedHash = null, onProgress = null) {
  if (!MOBILE) {
    // On web, just open the release page
    window.open('https://github.com/SmitroniX/SmiTriX/releases', '_blank', 'noopener')
    return
  }

  const { Filesystem, Directory } = await import('@capacitor/filesystem')

  // Download with progress tracking via ReadableStream
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Download failed: ${res.status}`)

  const total = parseInt(res.headers.get('content-length') || '0', 10)
  const reader = res.body.getReader()
  const chunks = []
  let received = 0

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    received += value.length
    if (onProgress) onProgress(received, total)
  }

  // Reassemble into a single blob
  const blob = new Blob(chunks)

  // Size check: an APK should be at least 100 KB
  if (blob.size < 100_000) {
    throw new Error('Downloaded file is too small to be a valid APK (' + blob.size + ' bytes)')
  }

  // SHA-256 integrity check
  if (expectedHash) {
    const buffer = await blob.arrayBuffer()
    const actualHash = await sha256(buffer)
    if (actualHash !== expectedHash.toLowerCase().trim()) {
      throw new Error('SHA-256 mismatch — download may be corrupted or tampered with')
    }
  }

  // Convert blob to base64
  const base64 = await new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result.split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })

  const fileName = 'smitrix-update.apk'
  await Filesystem.writeFile({
    path: fileName,
    directory: Directory.Cache,
    data: base64,
  })

  // Use the local InstallPlugin to trigger the Android package installer
  const { registerPlugin } = await import('@capacitor/core')
  const Install = registerPlugin('Install')
  await Install.installApk({ fileName })
}
