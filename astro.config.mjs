// @ts-check
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import react from "@astrojs/react";
import svgr from "vite-plugin-svgr";

import sitemap from "@astrojs/sitemap";

import cloudflare from "@astrojs/cloudflare";
import vercel from "@astrojs/vercel/serverless";
import node from "@astrojs/node";

const isVercel = process.env.VERCEL === "1";
const isCloudflare = process.env.CF_PAGES === "1";

let adapter;

if (isVercel) {
    adapter = vercel({
        webAnalytics: {
            enabled: true,
        },
        maxDuration: 8,
    });
} else if (isCloudflare) {
    adapter = cloudflare();
} else {
    adapter = node({
        mode: "standalone",
    });
}

// 只有 Cloudflare Workers 要用 WASM 版本的 satori / resvg，其餘（本機 dev、Vercel）跑在 Node 上
const cfWasmTarget = isCloudflare ? "workers" : "node";

/**
 * 讓 /clubs/a08 這種短網址導到完整的社團頁。
 * 直接從 content 目錄的檔名產生，新增社團時不必手動維護這份清單。
 *
 * @param {string} dir content 目錄（相對於本檔案）
 * @param {string} prefix 網址前綴，例如 "/clubs" 或 "/2025/clubs"
 * @returns {Record<string, string>}
 */
function buildClubRedirects(dir, prefix) {
    const contentDir = fileURLToPath(new URL(dir, import.meta.url));
    if (!fs.existsSync(contentDir)) return {};

    return Object.fromEntries(
        fs
            .readdirSync(contentDir)
            .filter((file) => file.endsWith(".md"))
            .map((file) => {
                const slug = path.basename(file, ".md").toLowerCase();
                const code = slug.split("-")[0];
                return [`${prefix}/${code}`, `${prefix}/${slug}/`];
            })
    );
}

const clubRedirects = {
    ...buildClubRedirects("./src/content/clubs", "/clubs"),
    ...buildClubRedirects("./src/content/clubs2025", "/2025/clubs"),
};

export default defineConfig({
    site: process.env.PUBLIC_SITE || "http://localhost:4321",
    redirects: {
        ...clubRedirects,
    },
    vite: {
        resolve: {
            // 用陣列形式才能以正規表達式做「完全相符」的比對，
            // 否則 @cf-wasm/satori -> @cf-wasm/satori/node 會再次命中自己而無限遞迴
            alias: [
                ...(isCloudflare ? [{ find: /^react-dom\/server$/, replacement: "react-dom/server.edge" }] : []),
                // @cf-wasm/* 的預設進入點是給 Workers 的 WASM 版本，
                // 在 Node（本機 dev 與 Vercel）底下會因為 Node 把 .wasm 當 ES module 解析而失敗
                // （Cannot find package 'a' imported from .../yoga.wasm），所以按執行環境指定進入點。
                { find: /^@cf-wasm\/satori$/, replacement: `@cf-wasm/satori/${cfWasmTarget}` },
                { find: /^@cf-wasm\/resvg$/, replacement: `@cf-wasm/resvg/${cfWasmTarget}` },
            ],
        },
        plugins: [
            tailwindcss(),
            svgr({
                include: "**/*.svg?react",
                svgrOptions: {
                    plugins: ["@svgr/plugin-svgo", "@svgr/plugin-jsx"],
                    svgoConfig: {
                        plugins: ["removeTitle", "removeDesc", "removeDoctype"],
                    },
                },
            }),
        ],
        optimizeDeps: {
            exclude: ["functions"],
        },
    },
    markdown: {
        remarkPlugins: ["remark-breaks"],
    },
    integrations: [
        react(),
        sitemap({
            // 封存年度的社團頁與地圖是 noindex，不必進 sitemap
            // （/2025/exhibition 是仍有閱讀價值的回顧文章，保留）
            filter: (page) => !/\/2025\/(clubs|map)/.test(page),
        }),
    ],

    build: {
        format: "directory",
    },

    adapter: adapter,
});
