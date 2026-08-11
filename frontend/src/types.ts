export type Role = "user" | "assistant";
export type MessageStatus = "pending" | "success" | "error" | "stopped";

export interface Source {
  title: string;
  source: string;
  department: string;
  page: string | number;
  url: string;
  id: string;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  timestamp: number;
  status: MessageStatus;
  sources?: Source[];
  errorCode?: string;
  originalQuestion?: string;
}

export interface ChatRecord {
  id: string;
  messages: Message[];
  updatedAt: number;
  title: string;
  preview: string;
}

export type ChatListItem = Pick<ChatRecord, "id" | "title" | "updatedAt" | "preview">;

export interface StorageErrorInfo {
  code: string;
  message: string;
  at: number;
}

export interface StorageResult {
  ok: boolean;
  error: StorageErrorInfo | null;
}

export interface ChatMetadata {
  updatedAt?: number;
  title?: string;
  preview?: string;
}

export interface AskQuestionResponse {
  answer: string;
  sources: Source[];
}
