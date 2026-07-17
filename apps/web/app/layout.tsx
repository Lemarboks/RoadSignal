import "./globals.css";
import "maplibre-gl/dist/maplibre-gl.css";
export const metadata = { title: "SafeRoute AI", description: "Real-time route-risk intelligence" };
export default function Layout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
