import { sites } from '@openai/sites-vite-plugin';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { cp, mkdir, readdir, rm } from 'node:fs/promises';
import { resolve } from 'node:path';

function sitesStaticAssets() {
  return {
    name: 'sites-static-assets',
    async closeBundle() {
      const outputDirectory = resolve('dist');
      const clientDirectory = resolve(outputDirectory, 'client');
      const entries = await readdir(outputDirectory, { withFileTypes: true });

      await rm(clientDirectory, { recursive: true, force: true });
      await mkdir(clientDirectory, { recursive: true });
      for (const entry of entries) {
        if (['.openai', 'client', 'server'].includes(entry.name)) continue;
        await cp(resolve(outputDirectory, entry.name), resolve(clientDirectory, entry.name), {
          recursive: entry.isDirectory(),
        });
      }

      await cp(resolve('.openai', 'drizzle'), resolve(outputDirectory, '.openai', 'drizzle'), {
        recursive: true,
      });
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [react(), sites(), sitesStaticAssets()],
});
