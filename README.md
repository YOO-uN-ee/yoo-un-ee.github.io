## Adding a publication poster

1. Put the PDF in `public/posters/`. For example, save it as `public/posters/my-conference-poster.pdf`.
2. Find the publication in `src/data/static.ts` or `src/data/dynamic.ts` and add a `poster` field inside its existing `links` object, alongside any `paper` or `github` links.

   ```ts
   "links": {
     "github": "https://github.com/owner/repository",
     "poster": "/posters/my-conference-poster.pdf"
   }
   ```

   You can also use a full URL to a hosted PDF.
3. Commit the publication update and any PDFs you added. Push to `main` to publish through GitHub Pages.

The **Poster** button opens the PDF in a new tab, just like the **CV** link.
