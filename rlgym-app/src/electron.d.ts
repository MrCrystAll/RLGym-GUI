export type UpdateState =
  | { status: 'idle' | 'checking' | 'up-to-date' | 'disabled' }
  | { status: 'available' | 'ready'; version: string }
  | { status: 'downloading'; percent: number }
  | { status: 'error'; message: string };

declare global {
  interface Window {
    rlgym?: {
      getBackendConfig(): Promise<{ port: number; token: string; baseUrl: string }>;
      updater: {
        check(): Promise<void>;
        download(): Promise<void>;
        install(): Promise<void>;
        onState(cb: (s: UpdateState) => void): () => void;
      };
    };
  }
}