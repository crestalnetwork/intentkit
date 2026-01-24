import Wrapper from "./Wrapper";

// Enable dynamic routes in static export mode
// Enable dynamic routes in static export mode
export function generateStaticParams() {
  return [{ id: "dummy", slug: "dummy" }];
}

export default function Page() {
  return <Wrapper />;
}
