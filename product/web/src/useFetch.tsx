import { type ReactNode, useEffect, useState } from "react";
import { type Lang, useLang } from "./i18n";

const COPY: Record<Lang, { loading: string; error: string }> = {
  en: { loading: "Loading…", error: "Error" },
  zh: { loading: "加载中…", error: "错误" },
};

export type Async<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

export function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = []): Async<T> {
  const [state, setState] = useState<Async<T>>({ status: "loading" });
  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    fn()
      .then((data) => active && setState({ status: "ready", data }))
      .catch(
        (e: unknown) =>
          active &&
          setState({ status: "error", message: e instanceof Error ? e.message : String(e) }),
      );
    return () => {
      active = false;
    };
    // deps are caller-controlled; fn identity is intentionally not tracked
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function Loadable<T>({
  state,
  children,
}: {
  state: Async<T>;
  children: (data: T) => ReactNode;
}) {
  const t = COPY[useLang().lang];
  if (state.status === "loading") return <p className="muted">{t.loading}</p>;
  if (state.status === "error")
    return (
      <p role="alert" className="error">
        {t.error}: {state.message}
      </p>
    );
  return <>{children(state.data)}</>;
}
