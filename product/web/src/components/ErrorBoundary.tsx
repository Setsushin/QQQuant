import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  label?: string;
  // Translated by the caller (App); a class component can't use the useLang hook.
  retryLabel?: string;
  failedText?: string;
}

interface State {
  err: Error | null;
}

// One panel's crash must not blank the whole shell. Class component because hooks
// can't catch render-phase errors.
export class ErrorBoundary extends Component<Props, State> {
  state: State = { err: null };

  static getDerivedStateFromError(err: Error): State {
    return { err };
  }

  componentDidCatch(err: Error, info: ErrorInfo): void {
    // Surface to the dev console; the user-visible message comes from render().
    console.error(`[${this.props.label ?? "panel"}] render failed`, err, info);
  }

  reset = (): void => {
    this.setState({ err: null });
  };

  render(): ReactNode {
    const { err } = this.state;
    if (!err) return this.props.children;
    return (
      <div role="alert" className="error">
        <p>
          <b>{this.props.label ?? "Panel"}</b> {this.props.failedText ?? "failed to render"}:{" "}
          {err.message}
        </p>
        <button type="button" onClick={this.reset}>
          {this.props.retryLabel ?? "Retry"}
        </button>
      </div>
    );
  }
}
