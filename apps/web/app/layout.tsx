import "./globals.css";
import "maplibre-gl/dist/maplibre-gl.css";
export const metadata = {
  title: "SafeRoute AI - Route-risk demonstration",
  description: "Compare Cape Town driving routes using confidence-weighted risk estimates in an interactive static demonstration.",
  applicationName: "SafeRoute AI",
  keywords: ["route planning", "road safety", "Cape Town", "fleet management"],
};
export default function Layout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
