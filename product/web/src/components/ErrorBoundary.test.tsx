import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, test, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

function Boom({ throwNow }: { throwNow: boolean }): JSX.Element {
  if (throwNow) throw new Error("kaboom");
  return <p>ok</p>;
}

function Harness(): JSX.Element {
  const [throwNow, setThrowNow] = useState(true);
  return (
    <div>
      <button type="button" onClick={() => setThrowNow(false)}>
        fix
      </button>
      <ErrorBoundary label="panel">
        <Boom throwNow={throwNow} />
      </ErrorBoundary>
    </div>
  );
}

test("catches a child render throw and renders a labelled message", () => {
  const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
  render(
    <ErrorBoundary label="distribution">
      <Boom throwNow={true} />
    </ErrorBoundary>,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("distribution");
  expect(screen.getByRole("alert")).toHaveTextContent("kaboom");
  spy.mockRestore();
});

test("retry button resets state so a now-healthy child re-renders", () => {
  const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
  render(<Harness />);
  expect(screen.getByRole("alert")).toBeInTheDocument();
  fireEvent.click(screen.getByText("fix"));
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(screen.getByText("ok")).toBeInTheDocument();
  spy.mockRestore();
});
