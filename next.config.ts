import type { NextConfig } from "next";
const nextConfig: NextConfig = {reactStrictMode:true,webpack:(config,{isServer})=>{if(!isServer)config.resolve.fallback={...(config.resolve.fallback||{}),fs:false,https:false,http:false,crypto:false,stream:false};return config}};
export default nextConfig;
