import { defineConfig } from 'vite-plus'

export default defineConfig({
  lint: { options: { typeAware: true, typeCheck: true } },
  fmt: {
    printWidth: 100,
    tabWidth: 2,
    singleQuote: true,
    trailingComma: 'es5',
    semi: false,
    arrowParens: 'always',
    sortPackageJson: false,
    ignorePatterns: ['*.html', 'dist/', 'node_modules/', '*.min.js', 'lib/*', 'pnpm-lock.yaml'],
  },
})
