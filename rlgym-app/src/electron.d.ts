// notes: the release's changelog section as HTML (unsanitized). date: ISO string.
export interface ReleaseInfo {
  version: string;
  notes: string | null;
  date: string | null;
}

export type UpdateState =
  | { status: 'idle' | 'checking' | 'up-to-date' | 'disabled' }
  | ({ status: 'available' | 'ready' } & ReleaseInfo)
  | { status: 'downloading'; percent: number }
  | { status: 'error'; message: string };

declare global {
  interface Window {
    rlgym?: {
      getBackendConfig(): Promise<{ port: number; token: string; baseUrl: string }>;
      // Native file dialog; null when cancelled.
      openFile(options?: {
        title?: string;
        filters?: { name: string; extensions: string[] }[];
      }): Promise<string | null>;
      // Native "save as" dialog that writes `content` to the chosen file; its path, or null when cancelled.
      saveFile(options: {
        title?: string;
        defaultName?: string;
        filters?: { name: string; extensions: string[] }[];
        content: string;
      }): Promise<string | null>;
      updater: {
        check(): Promise<void>;
        download(): Promise<void>;
        install(): Promise<void>;
        onState(cb: (s: UpdateState) => void): () => void;
      };
    };
  }
}