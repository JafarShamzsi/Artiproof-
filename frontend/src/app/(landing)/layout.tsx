import { SmoothScrollProvider } from "@/components/landing/SmoothScrollProvider";

export default function LandingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <SmoothScrollProvider>{children}</SmoothScrollProvider>;
}
