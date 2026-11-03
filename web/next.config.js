/** @type {import('next').NextConfig} */
const nextConfig = {
  // מאפשר ל-@huggingface/transformers לטעון מודלים ב-Node (server-side)
  serverExternalPackages: ["@huggingface/transformers"],
  devIndicators: false,
};
module.exports = nextConfig;
