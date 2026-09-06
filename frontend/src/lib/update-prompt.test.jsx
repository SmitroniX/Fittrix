// @vitest-environment happy-dom
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { compareSemver, shouldShowUpdatePrompt, remindUpdateLater, clearUpdateReminder, REMIND_STORAGE_KEY } from './update.js'
import { UpdatePromptDialog, promptUpdate } from '../components/UpdateDialog.jsx'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

describe('Update logic & reminder behavior', () => {
  beforeEach(() => {
    localStorage.clear()
    clearUpdateReminder()
  })

  describe('compareSemver', () => {
    it('correctly compares version numbers', () => {
      expect(compareSemver('1.3.6', '1.3.5')).toBe(1)
      expect(compareSemver('1.3.5', '1.3.6')).toBe(-1)
      expect(compareSemver('1.3.6', '1.3.6')).toBe(0)
      expect(compareSemver('v1.3.6', '1.3.5')).toBe(1)
      expect(compareSemver('1.4.0', '1.3.9')).toBe(1)
      expect(compareSemver('2.0.0', '1.9.9')).toBe(1)
      expect(compareSemver('1.3.0', '1.3.0')).toBe(0)
    })
  })

  describe('shouldShowUpdatePrompt and remindUpdateLater', () => {
    it('returns false if there is no update', () => {
      expect(shouldShowUpdatePrompt(null)).toBe(false)
      expect(shouldShowUpdatePrompt({ hasUpdate: false, latestVersion: '1.3.6' })).toBe(false)
      expect(shouldShowUpdatePrompt({ hasUpdate: true, latestVersion: '' })).toBe(false)
    })

    it('returns true when a newer version is available and no reminder exists', () => {
      const info = { hasUpdate: true, latestVersion: '1.3.7' }
      expect(shouldShowUpdatePrompt(info)).toBe(true)
    })

    it('returns false when user tapped remind me later within 24 hours', () => {
      const info = { hasUpdate: true, latestVersion: '1.3.7' }
      remindUpdateLater('1.3.7')
      expect(shouldShowUpdatePrompt(info)).toBe(false)
    })

    it('returns true when reminded for a previous version but a newer version is released', () => {
      remindUpdateLater('1.3.6')
      const newerInfo = { hasUpdate: true, latestVersion: '1.3.7' }
      expect(shouldShowUpdatePrompt(newerInfo)).toBe(true)
    })

    it('returns true when 24 hours have elapsed since reminder', () => {
      const pastTime = Date.now() - (25 * 60 * 60 * 1000)
      localStorage.setItem(REMIND_STORAGE_KEY, JSON.stringify({ version: '1.3.7', timestamp: pastTime }))
      const info = { hasUpdate: true, latestVersion: '1.3.7' }
      expect(shouldShowUpdatePrompt(info)).toBe(true)
    })
  })
})

describe('UpdatePromptDialog UI', () => {
  let host, root

  beforeEach(() => {
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
    localStorage.clear()
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
  })

  it('renders update prompt with version and buttons', () => {
    const updateInfo = {
      hasUpdate: true,
      latestVersion: '1.4.0',
      apkUrl: 'https://example.com/smitrix.apk',
      hashUrl: 'https://example.com/smitrix.apk.sha256'
    }
    const close = vi.fn()

    act(() => {
      root.render(<UpdatePromptDialog updateInfo={updateInfo} close={close} />)
    })

    expect(host.textContent).toContain('1.4.0')
    expect(host.textContent).toContain('Update now')
    expect(host.textContent).toContain('Remind me later')
  })

  it('records reminder and closes when Remind me later is clicked', () => {
    const updateInfo = {
      hasUpdate: true,
      latestVersion: '1.4.0',
      apkUrl: 'https://example.com/smitrix.apk'
    }
    const close = vi.fn()

    act(() => {
      root.render(<UpdatePromptDialog updateInfo={updateInfo} close={close} />)
    })

    const remindBtn = [...host.querySelectorAll('button')].find(b => b.textContent.includes('Remind me later'))
    expect(remindBtn).toBeTruthy()

    act(() => {
      remindBtn.click()
    })

    expect(close).toHaveBeenCalledTimes(1)
    // Verify stored in localStorage
    const stored = JSON.parse(localStorage.getItem(REMIND_STORAGE_KEY))
    expect(stored.version).toBe('1.4.0')
    expect(stored.timestamp).toBeGreaterThan(0)
  })
})
