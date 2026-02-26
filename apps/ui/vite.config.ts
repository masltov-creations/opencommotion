import { defineConfig } from 'vitest/config'
import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const uiPackageJson = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8')) as { version?: string }
const rootPackageJson = JSON.parse(readFileSync(resolve(__dirname, '../../package.json'), 'utf-8')) as { version?: string }
const uiVersion = rootPackageJson.version || uiPackageJson.version || '0.0.0'

let uiRevision = 'dev'
try {
  uiRevision = execSync('git rev-parse --short HEAD', {
    cwd: resolve(__dirname, '../..'),
    stdio: ['ignore', 'pipe', 'ignore'],
    encoding: 'utf-8',
  }).trim()
} catch {
  uiRevision = 'dev'
}

export default defineConfig({
  define: {
    __OPENCOMMOTION_UI_VERSION__: JSON.stringify(uiVersion),
    __OPENCOMMOTION_UI_REVISION__: JSON.stringify(uiRevision || 'dev'),
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
