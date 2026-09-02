import { defineConfig } from 'vitepress'

/**
 * Docs for Radiowriter, published to GitHub Pages.
 *
 * `base` is the repository name because the site is served from
 * gmadevs.github.io/Radiowriter rather than from a domain of its own.
 */
export default defineConfig({
  title: 'Radiowriter',
  description:
    'Find the literature for a Radiopaedia article, screen it, and write the article against it',
  base: '/Radiowriter/',
  lang: 'en',
  cleanUrls: true,
  lastUpdated: true,
  appearance: 'dark',

  themeConfig: {
    nav: [
      { text: 'Guide', link: '/guide/install' },
      { text: 'How it works', link: '/internals/architecture' },
      { text: 'Develop', link: '/develop/run' },
      { text: 'Limitations', link: '/limitations' }
    ],

    sidebar: [
      {
        text: 'Using it',
        items: [
          { text: 'Install and first run', link: '/guide/install' },
          { text: 'Search PubMed', link: '/guide/search' },
          { text: 'Build a query in blocks', link: '/guide/blocks' },
          { text: 'Screen what comes back', link: '/guide/screen' },
          { text: 'Journal quartiles and open access', link: '/guide/journals' },
          { text: 'Write the article', link: '/guide/write' },
          { text: 'Backup and moving computer', link: '/guide/backup' }
        ]
      },
      {
        text: 'How it works',
        items: [
          { text: 'Architecture', link: '/internals/architecture' },
          { text: 'Where the data lives', link: '/internals/storage' },
          { text: 'Matching journals to SCImago', link: '/internals/journals' },
          { text: 'The services it calls', link: '/internals/services' }
        ]
      },
      {
        text: 'Development',
        items: [
          { text: 'Run from source', link: '/develop/run' },
          { text: 'Tests', link: '/develop/tests' },
          { text: 'Releasing to PyPI', link: '/develop/release' }
        ]
      },
      {
        text: 'Reference',
        items: [{ text: 'Known limitations', link: '/limitations' }]
      }
    ],

    socialLinks: [{ icon: 'github', link: 'https://github.com/gmadevs/Radiowriter' }],

    search: { provider: 'local' },

    editLink: {
      pattern: 'https://github.com/gmadevs/Radiowriter/edit/main/docs/:path',
      text: 'Edit this page on GitHub'
    },

    footer: {
      message:
        'AGPL-3.0-only · Unofficial, not affiliated with or endorsed by Radiopaedia.org',
      copyright: '© Giorgio Maria Agazzi'
    }
  }
})
