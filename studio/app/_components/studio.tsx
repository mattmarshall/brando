"use client";

/**
 * The studio: a brief goes in, nine agents work, a brand comes out.
 *
 * ONE PAGE, THREE STATES, and no route change between them — the run is the
 * same object throughout, so the floor, the transcript and the finished brand
 * are three views of one stream rather than three pages that have to agree.
 *
 * The transcript is kept, not hidden behind the pretty view. A studio you
 * cannot watch argue with itself is a studio you have to trust; the critic's
 * blocking findings and the director's overrides are the most interesting
 * thing on the page when they happen.
 */
import { useEveAgent } from "eve/react";
import { AlertCircleIcon, BrainIcon, SquareIcon } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";

import type { Brief } from "@/agent/lib/brand";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent } from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputButton,
  type PromptInputMessage,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { AgentMessage } from "./agent-message";
import { BrandView } from "./brand-view";
import { BriefForm, briefMessage } from "./brief-form";
import { Floor } from "./floor";
import { readRun } from "./run-state";

export function Studio({
  account,
  sessionId,
}: {
  readonly account?: ReactNode;
  readonly sessionId?: string;
}) {
  const [cancellationError, setCancellationError] = useState<string>();
  const agent = useEveAgent({
    initialSession: sessionId === undefined ? undefined : { sessionId, streamIndex: 0 },
    resume: sessionId !== undefined,
    onSessionChange(session) {
      if (sessionId === undefined && session !== undefined) {
        // Next patches window.history to navigate, which would detach the
        // active stream — so the URL is rewritten underneath it instead.
        History.prototype.replaceState.call(
          window.history,
          window.history.state,
          "",
          `/s/${encodeURIComponent(session.sessionId)}`,
        );
      }
    },
  });

  const run = useMemo(() => readRun(agent.data.messages), [agent.data.messages]);
  const isBusy = agent.status === "submitted" || agent.status === "streaming";
  const isResuming = agent.status === "resuming";
  const started = run.started || agent.data.messages.length > 0 || isResuming;
  const errorMessage = cancellationError ?? agent.error?.message;

  const brief = (value: Brief) => {
    setCancellationError(undefined);
    void agent.send(briefMessage(value));
  };

  const steer = async (message: PromptInputMessage) => {
    const text = message.text.trim();
    if (text.length === 0 || isResuming) return;
    setCancellationError(undefined);
    await agent.send(text, isBusy ? { turnPolicy: "steer" as const } : undefined);
  };

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <TopBar account={account} />

      {started ? (
        <div className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 gap-8 px-4 py-6 lg:grid-cols-[280px_minmax(0,1fr)] lg:px-8">
          <aside className="lg:sticky lg:top-20 lg:self-start">
            <Floor run={run} />
          </aside>

          <main className="flex min-w-0 flex-col gap-8">
            {run.spec ? (
              <BrandView onSaved={() => undefined} spec={run.spec} />
            ) : run.specError ? (
              <Problem
                text={`The director submitted a brand that is not a legal BrandSpec — ${run.specError}`}
              />
            ) : null}

            <section className="flex min-w-0 flex-col">
              <h2 className="mb-2 text-muted-foreground text-xs uppercase tracking-wide">
                The studio, talking
              </h2>
              <Conversation className="max-h-[70vh] min-h-48" resize="smooth">
                <ConversationContent className="gap-6 px-0 pb-4">
                  {agent.data.messages.map((message, index) => (
                    <AgentMessage
                      canRespond={!isBusy && !isResuming}
                      isStreaming={agent.status === "streaming" && index === agent.data.messages.length - 1}
                      key={message.id}
                      message={message}
                      onInputResponses={(responses) => {
                        setCancellationError(undefined);
                        return agent.respond(responses);
                      }}
                    />
                  ))}
                  {isBusy ? <Working /> : null}
                  {errorMessage ? <Problem text={errorMessage} /> : null}
                </ConversationContent>
                <ConversationScrollButton />
              </Conversation>
            </section>

            <div className="sticky bottom-4">
              <PromptInput onSubmit={steer}>
                <PromptInputTextarea
                  disabled={isResuming}
                  placeholder={isBusy ? "Steer the director…" : "Ask for a revision…"}
                />
                {isBusy ? (
                  <PromptInputButton
                    aria-label="Stop"
                    className="absolute right-2.5 bottom-2.5"
                    onClick={() => {
                      setCancellationError(undefined);
                      void agent.cancel().catch((error: unknown) => {
                        setCancellationError(
                          error instanceof Error ? error.message : "Unable to stop the run.",
                        );
                      });
                    }}
                    variant="outline"
                  >
                    <SquareIcon className="size-3 fill-current" />
                  </PromptInputButton>
                ) : (
                  <PromptInputSubmit disabled={isResuming} />
                )}
              </PromptInput>
            </div>
          </main>
        </div>
      ) : (
        <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-8 px-4 py-12">
          <div>
            <h1 className="font-medium text-4xl tracking-tighter">Brief the studio</h1>
            <p className="mt-2 text-muted-foreground">
              Nine agents: a director and eight specialists. Every colour is gated on contrast the
              studio computes rather than estimates, and the mark is a program brando executes — the
              model never draws.
            </p>
          </div>
          <BriefForm onSubmit={brief} />
        </main>
      )}
    </div>
  );
}

function TopBar({ account }: { readonly account?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-4 lg:px-8">
      <Link className="font-medium text-sm tracking-tight" href="/">
        brando studio
      </Link>
      <nav className="flex items-center gap-4">
        <Link className="text-muted-foreground text-sm hover:text-foreground" href="/gallery">
          Catalog
        </Link>
        <Link className="text-muted-foreground text-sm hover:text-foreground" href="/">
          New brief
        </Link>
        {account}
      </nav>
    </header>
  );
}

function Working() {
  return (
    <Message aria-live="polite" from="assistant">
      <MessageContent>
        <div className="flex w-full items-center gap-2 text-muted-foreground text-sm">
          <BrainIcon className="size-4" />
          <Shimmer duration={1}>Working</Shimmer>
        </div>
      </MessageContent>
    </Message>
  );
}

function Problem({ text }: { readonly text: string }) {
  return (
    <div
      className="flex w-full items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm"
      role="alert"
    >
      <AlertCircleIcon className="mt-0.5 size-4 shrink-0 text-destructive" />
      <span>{text}</span>
    </div>
  );
}
