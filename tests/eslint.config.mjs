import js from '@eslint/js';
import html from 'eslint-plugin-html';
import globals from 'globals';
import tseslint from 'typescript-eslint';

const typescriptRules = tseslint.configs.recommended.map(config => ({ ...config, files: ['**/*.ts'] }));

export default [
  { ignores: ['node_modules/**', 'test-results/**', 'playwright-report/**'] },
  js.configs.recommended,
  ...typescriptRules,
  {
    files: ['**/*.html'],
    plugins: { html },
    languageOptions: { sourceType: 'script', globals: globals.browser },
  },
  {
    files: ['**/dashboard/index.html'],
    languageOptions: { globals: { d3: 'readonly', dash: 'readonly' } },
  },
];
