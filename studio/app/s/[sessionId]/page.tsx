import { AuthenticatedStudio } from "@/app/_components/authenticated-studio";

export default async function RunPage({
  params,
}: {
  readonly params: Promise<{ readonly sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <AuthenticatedStudio sessionId={sessionId} />;
}
