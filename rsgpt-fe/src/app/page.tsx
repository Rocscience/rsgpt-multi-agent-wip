import type {Metadata} from "next";
import Dashboard from "@/components/dashboard/dashboard";

export const metadata: Metadata = {
  title: "RSInsight",
  description: "Engineering Intelligence at Your Fingertips",
};

export default async function Home() {

  return (
    <>
      <Dashboard />
    </>
  );
}