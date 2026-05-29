import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test } from "vitest";
import { LangProvider, useLang } from "./i18n";

function Probe() {
  const { lang, setLang } = useLang();
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <button type="button" onClick={() => setLang(lang === "en" ? "zh" : "en")}>
        flip
      </button>
    </div>
  );
}

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

test("useLang() falls back to en without a provider", () => {
  render(<Probe />);
  expect(screen.getByTestId("lang")).toHaveTextContent("en");
});

test("provider switch updates consumers", () => {
  render(
    <LangProvider>
      <Probe />
    </LangProvider>,
  );
  expect(screen.getByTestId("lang")).toHaveTextContent("en");
  fireEvent.click(screen.getByText("flip"));
  expect(screen.getByTestId("lang")).toHaveTextContent("zh");
});

test("the choice round-trips through localStorage", () => {
  localStorage.setItem("qqquant.lang", "zh");
  render(
    <LangProvider>
      <Probe />
    </LangProvider>,
  );
  expect(screen.getByTestId("lang")).toHaveTextContent("zh"); // read on init
  fireEvent.click(screen.getByText("flip"));
  expect(localStorage.getItem("qqquant.lang")).toBe("en"); // written on change
});
