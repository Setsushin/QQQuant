import { useLang } from "../i18n";
import { strategyMeta } from "../strategies";

// Two-line cell: bold strategy code on top, plain-language description below.
// Centralized so every table that lists strategies reads the same way.
export function StrategyCell({ name }: { name: string }) {
  const meta = strategyMeta(name, useLang().lang);
  return (
    <div className="strategy-cell">
      <div className="strategy-code">{meta.code}</div>
      {meta.description && <div className="strategy-desc muted">{meta.description}</div>}
    </div>
  );
}
