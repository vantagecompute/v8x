import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import * as fs from 'fs';
import * as path from 'path';
import {staticDir} from '@vantagecompute/docusaurus-theme';

// Function to read version from pyproject.toml
function getVersionFromPyproject(): string {
  try {
    const pyprojectPath = path.join(__dirname, '../pyproject.toml');
    const content = fs.readFileSync(pyprojectPath, 'utf8');
    
    // Extract version using regex
    const versionMatch = content.match(/^version\s*=\s*["']([^"']+)["']/m);
    
    if (versionMatch) {
      return versionMatch[1];
    }
    
    throw new Error('Version not found in pyproject.toml');
  } catch (error) {
    console.error('Error reading version from pyproject.toml:', error);
    return '0.0.0'; // fallback version
  }
}

const projectVersion = getVersionFromPyproject();

const config: Config = {
  title: 'v8x',
  tagline: `A powerful Python CLI for interacting with the Vantage platform (v${projectVersion})`,
  favicon: 'img/favicon.ico',

  url: 'https://vantagecompute.github.io',
  baseUrl: '/v8x/',

  organizationName: 'vantagecompute',
  projectName: 'v8x',
  deploymentBranch: 'main',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  markdown: {
    format: 'detect',
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn'
    }
  },
  themes: ['@docusaurus/theme-mermaid', '@vantagecompute/docusaurus-theme'],

  staticDirectories: ['static', staticDir],

  presets: [
    [
      'classic',
      {
        docs: {
          path: './docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/vantagecompute/v8x/tree/main/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      },
    ],
  ],
  plugins: [
    [ 
      'docusaurus-plugin-llms',
      {
        // Options here
        generateLLMsTxt: true,
        generateLLMsFullTxt: true,
        docsDir: 'docs',
        ignoreFiles: ['advanced/*', 'private/*'],
        title: 'Vantage Compute CLI Documentation',
          description: 'Complete platform, CLI documentation for Vantage Compute.',
          includeBlog: false,
          // Content cleaning options
          excludeImports: true,
          removeDuplicateHeadings: true,
          // Generate individual markdown files following llmstxt.org specification
          generateMarkdownFiles: true,
          // Control documentation order
          includeOrder: [],
          includeUnmatchedLast: true,
          // Path transformation options
          pathTransformation: {
            // Paths to ignore when constructing URLs (will be removed if found)
            ignorePaths: ['docs'],
            // Paths to add when constructing URLs (will be prepended if not already present)
            // addPaths: ['api'],
          },
          // Custom LLM files for specific documentation sections
          customLLMFiles: [
            {
              filename: 'llms-index.txt',
              includePatterns: ['docs/index.md'],
              fullContent: true,
              title: 'v8x Documentation Index',
              description: 'Index reference for v8x'
            },
            {
              filename: 'llms-usage.txt',
              includePatterns: ['docs/usage.md'],
              fullContent: true,
              title: 'v8x Usage Documentation',
              description: 'Usage documentation for v8x'
             },
            {
              filename: 'llms-commands.txt',
              includePatterns: ['docs/commands.md'],
              fullContent: true,
              title: 'v8x Commands Documentation',
              description: 'Commands documentation for v8x'
            },
            {
              filename: 'llms-contributing.txt',
              includePatterns: ['docs/contributing.md'],
              fullContent: true,
              title: 'v8x Contributing Documentation',
              description: 'Contributing documentation for v8x'
            },
            {
              filename: 'llms-troubleshooting.txt',
              includePatterns: ['docs/troubleshooting.md'],
              fullContent: true,
              title: 'v8x Troubleshooting Documentation',
              description: 'Troubleshooting documentation for v8x'
            },
            {
              filename: 'llms-installation.txt',
              includePatterns: ['docs/installation.md'],
              fullContent: true,
              title: 'v8x Installation Documentation',
              description: 'Installation documentation for v8x'
            },
            {
              filename: 'llms-architecture.txt',
              includePatterns: ['docs/architecture.md'],
              fullContent: true,
              title: 'v8x Architecture Documentation',
              description: 'Architecture documentation for v8x'
            },
            {
              filename: 'llms-contact.txt',
              includePatterns: ['docs/contact.md'],
              fullContent: true,
              title: 'v8x Contact Documentation',
              description: 'Contact documentation for v8x'
            },
          ],
        },
    ],
  ],

  customFields: {
    projectVersion: projectVersion,
  },

  themeConfig: {
    navbar: {
      title: `v8x Documentation v${projectVersion}`,
      logo: {
        alt: 'Vantage Compute Logo',
        src: 'https://vantage-compute-public-assets.s3.us-east-1.amazonaws.com/branding/vantage-logo-text-white-horz.png',
        srcDark: 'https://vantage-compute-public-assets.s3.us-east-1.amazonaws.com/branding/vantage-logo-text-white-horz.png',
        href: 'https://vantagecompute.github.io/v8x/',
        target: '_self',
      },
      items: [
        {
          href: 'https://pypi.org/project/v8x/',
          label: 'PyPI',
          position: 'right',
          className: 'pypi-button',
        },
        {
          href: 'https://github.com/vantagecompute/v8x',
          label: 'GitHub',
          position: 'right',
          className: 'github-button',
        },
      ],
    },
    footer: {
      style: 'dark',
      logo: {
        alt: 'Vantage Compute Logo',
        src: 'https://vantage-compute-public-assets.s3.us-east-1.amazonaws.com/branding/vantage-logo-text-white-horz.png',
        href: 'https://vantagecompute.ai',
      },
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Installation',
              to: '/installation',
            },
            {
              label: 'Usage Examples',
              to: '/usage',
            },
            {
              label: 'Notebooks',
              to: '/notebooks',
            },
            {
              label: 'Deployment Applications',
              to: '/deployment-applications',
            },
            {
              label: 'Partner Vantage Installation',
              to: '/private-vantage-installation',
            },
            {
              label: 'Commands',
              to: '/commands',
            },
          ],
        },

        {
          title: 'Community',
          items: [
            {
              label: 'GitHub Discussions',
              href: 'https://github.com/vantagecompute/v8x/discussions',
            },
            {
              label: 'Issues',
              href: 'https://github.com/vantagecompute/v8x/issues',
            },
            {
              label: 'Support',
              href: 'https://vantagecompute.ai/support',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/vantagecompute/v8x',
            },
            {
              label: 'Vantage Compute',
              href: 'https://vantagecompute.ai',
            },
            {
              label: 'PyPI',
              href: 'https://pypi.org/project/v8x/',
            },
          ],
        },
      ],
      copyright: 'Copyright &copy; ' + new Date().getFullYear() + ' Vantage Compute.',
    },
    prism: {
    // dracula
    // duotoneDark
    // duotoneLight
    // github
    // gruvboxMaterialDark
    // gruvboxMaterialLight
    // jettwaveDark
    // jettwaveLight
    // nightOwl
    // nightOwlLight
    // oceanicNext
    // okaidia
    // oneDark
    // oneLight
    // palenight
    // shadesOfPurple
    // synthwave84
    // ultramin
    // vsDark
    // vsLight
      theme: prismThemes.vsLight,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['shell-session', 'python', 'bash'],
    },
    tableOfContents: {
      minHeadingLevel: 2,
      maxHeadingLevel: 5,
    },
  },
};

export default config;
