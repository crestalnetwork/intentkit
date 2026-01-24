import Wrapper from "./Wrapper";

// Enable dynamic routes in static export mode
export const dynamicParams = false;
export function generateStaticParams() {
  return [{ id: "dummy" }];
}

export default function Page() {
  return <Wrapper />;
}
