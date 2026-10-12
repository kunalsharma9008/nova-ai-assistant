"use client";



import { useEffect, useRef, useState } from "react";



type Source = {
  title?: string;
  url?: string;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  sources?: Array<Source | string>;
  generatedFiles?: Array<{ path: string; content: string }>;
  generatedProjectName?: string;
  generatedSummary?: string;
};

type Conversation = {
  id: string;
  title?: string;
  first_message?: string;
  updated_at?: string;
  created_at?: string;
};

/** Render Markdown-style fenced code blocks with a one-click copy control. */
function renderMessageContent(content: string) {
  const fence = /```([\w.+#-]*)[ \t]*\n([\s\S]*?)```/g;
  const parts: Array<{ type: "text" | "code"; value: string; language?: string; key: number }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = fence.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: content.slice(lastIndex, match.index), key: key++ });
    }
    parts.push({ type: "code", value: match[2].replace(/\n$/, ""), language: match[1] || "code", key: key++ });
    lastIndex = fence.lastIndex;
  }
  if (lastIndex < content.length || parts.length === 0) {
    parts.push({ type: "text", value: content.slice(lastIndex), key: key++ });
  }

  return parts.map((part) => part.type === "text" ? (
    <span key={part.key} className="whitespace-pre-wrap">{part.value}</span>
  ) : (
    <div key={part.key} className="nova-code-block my-4 overflow-hidden rounded-xl border border-white/10 bg-[#080b0a] text-gray-200">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 bg-white/[0.04] px-3 py-2">
        <span className="text-xs font-medium text-gray-400">{part.language}</span>
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(part.value);
            } catch {
              const textarea = document.createElement("textarea");
              textarea.value = part.value;
              textarea.style.position = "fixed";
              textarea.style.opacity = "0";
              document.body.appendChild(textarea);
              textarea.select();
              document.execCommand("copy");
              textarea.remove();
            }
          }}
          className="rounded-md border border-white/10 px-2.5 py-1 text-xs text-gray-300 transition hover:border-white/40 hover:text-white"
          aria-label={`Copy ${part.language} code`}
        >
          Copy code
        </button>
      </div>
      <pre className="max-h-[520px] overflow-auto p-4 text-xs leading-6"><code>{part.value}</code></pre>
    </div>
  ));
}

const BACKEND_URL = "http://127.0.0.1:8000";




export default function Home() {

  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversationActionId, setConversationActionId] = useState<string | null>(null);
  const [input, setInput] = useState("");

  const [loading, setLoading] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [codingMode, setCodingMode] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);



  const [uploading, setUploading] = useState(false);

  const [uploadMessage, setUploadMessage] = useState("");



  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [voiceRepliesEnabled, setVoiceRepliesEnabled] = useState(true);
  const [voiceStatus, setVoiceStatus] = useState("");





  // Restore the user's theme preference and keep it across reloads.
  useEffect(() => {
    try {
      const savedTheme = window.localStorage.getItem("nova-theme");
      if (savedTheme === "light" || savedTheme === "dark") setTheme(savedTheme);
    } catch {
      // Theme still works for this session if storage is unavailable.
    }
  }, []);

  function toggleTheme() {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      try { window.localStorage.setItem("nova-theme", next); } catch { /* optional persistence */ }
      return next;
    });
  }

  // ==========================================================
  // CONVERSATION HISTORY
  // ==========================================================

  async function refreshConversations() {
    try {
      const response = await fetch(`${BACKEND_URL}/conversations`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Could not load chats (${response.status})`);
      const data = await response.json();
      setConversations(Array.isArray(data.conversations) ? data.conversations : []);
    } catch (error) {
      console.error("Could not load Nova conversations:", error);
    }
  }

  useEffect(() => {
    void refreshConversations();
  }, []);

  async function openConversation(conversationId: string) {
    if (loading || conversationActionId) return;
    setConversationActionId(conversationId);
    try {
      const response = await fetch(
        `${BACKEND_URL}/conversations/${encodeURIComponent(conversationId)}`,
        { cache: "no-store" }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not open this conversation.");
      }
      const loadedMessages = Array.isArray(data.messages) ? data.messages : [];
      setMessages(
        loadedMessages
          .filter((item: { role?: string; content?: string }) =>
            (item.role === "user" || item.role === "assistant") && typeof item.content === "string"
          )
          .map((item: { role: "user" | "assistant"; content: string }) => ({
            role: item.role,
            content: item.content,
          }))
      );
      setCurrentConversationId(conversationId);
      setSidebarOpen(false);
      setInput("");
      setUploadMessage("");
    } catch (error) {
      console.error("Could not open conversation:", error);
      alert(error instanceof Error ? error.message : "Could not open this conversation.");
    } finally {
      setConversationActionId(null);
    }
  }

  function newChat() {
    if (loading || conversationActionId) return;
    // A blank home screen is not a conversation, so don't create a history entry
    // until the user sends the first message.
    setCurrentConversationId(null);
    setMessages([]);
    setInput("");
    setUploadMessage("");
    setSidebarOpen(false);
  }

  async function renameChat(conversation: Conversation) {
    const currentTitle = conversation.title || conversation.first_message || "New Chat";
    const title = window.prompt("Enter a new chat name:", currentTitle);
    if (title === null) return;
    if (!title.trim()) {
      alert("Chat name cannot be empty.");
      return;
    }
    try {
      const response = await fetch(
        `${BACKEND_URL}/conversations/${encodeURIComponent(conversation.id)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: title.trim() }),
        }
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not rename this chat.");
      await refreshConversations();
    } catch (error) {
      console.error("Could not rename conversation:", error);
      alert(error instanceof Error ? error.message : "Could not rename this chat.");
    }
  }

  async function deleteChat(conversation: Conversation) {
    const title = conversation.title || conversation.first_message || "this chat";
    if (!window.confirm(`Delete "${title}"? This cannot be undone.`)) return;
    try {
      const response = await fetch(
        `${BACKEND_URL}/conversations/${encodeURIComponent(conversation.id)}`,
        { method: "DELETE" }
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not delete this chat.");
      if (currentConversationId === conversation.id) {
        setCurrentConversationId(null);
        setMessages([]);
        setInput("");
      }
      await refreshConversations();
    } catch (error) {
      console.error("Could not delete conversation:", error);
      alert(error instanceof Error ? error.message : "Could not delete this chat.");
    }
  }

  // ==========================================================
  // VOICE INPUT + SPOKEN REPLIES (English - India)
  // ==========================================================

  function stopSpeaking() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }

  function speakReply(text: string) {
    if (!voiceRepliesEnabled || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    stopSpeaking();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.rate = 1;
    utterance.pitch = 1;
    const voices = window.speechSynthesis.getVoices();
    const indianEnglishVoice = voices.find((voice) => voice.lang.toLowerCase() === "en-in")
      || voices.find((voice) => voice.lang.toLowerCase().startsWith("en-in"));
    if (indianEnglishVoice) utterance.voice = indianEnglishVoice;
    window.speechSynthesis.speak(utterance);
  }

  async function toggleListening() {
    if (isListening) {
      mediaRecorderRef.current?.stop();
      setVoiceStatus("Stopping recording and transcribing offline audio…");
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setVoiceStatus("Audio recording is not supported by this browser. Try Chrome or Edge.");
      return;
    }

    stopSpeaking();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      audioChunksRef.current = [];
      const preferredType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "";
      const recorder = new MediaRecorder(stream, preferredType ? { mimeType: preferredType } : undefined);
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        setIsListening(false);
        setVoiceStatus("Recording failed. Check microphone permission and try again.");
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      };
      recorder.onstop = async () => {
        setIsListening(false);
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        audioChunksRef.current = [];
        if (!audioBlob.size) {
          setVoiceStatus("No audio was captured. Please try speaking again.");
          return;
        }
        setVoiceStatus("Transcribing with Nova's offline speech recognizer…");
        try {
          const formData = new FormData();
          const extension = audioBlob.type.includes("mp4") ? "audio.mp4" : "audio.webm";
          formData.append("file", audioBlob, extension);
          const response = await fetch(`${BACKEND_URL}/transcribe`, { method: "POST", body: formData });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || data.error || "Offline transcription failed.");
          const transcript = typeof data.text === "string" ? data.text.trim() : "";
          if (!transcript) {
            setVoiceStatus("I couldn't hear clear speech. Please try again, closer to the microphone.");
            return;
          }
          setInput((current) => current.trim() ? `${current.trim()} ${transcript}` : transcript);
          setVoiceStatus("Voice captured offline. Review the text, then press send.");
        } catch (error) {
          setVoiceStatus(error instanceof Error ? error.message : "Offline transcription failed.");
        }
      };
      recorder.start();
      setIsListening(true);
      setVoiceStatus("Recording… speak in English (India), then tap the microphone again to finish.");
    } catch (error) {
      setIsListening(false);
      const message = error instanceof Error ? error.message : "Could not access the microphone.";
      setVoiceStatus(message.toLowerCase().includes("permission") || message.toLowerCase().includes("denied")
        ? "Microphone access was blocked. Allow microphone permission in your browser."
        : `Could not start microphone recording: ${message}`);
    }
  }

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // ==========================================================
  // CODING MODE PROJECT FILE CREATION
  // ==========================================================

  async function createGeneratedProject(message: Message) {
    const files = message.generatedFiles;
    if (!files?.length || creatingProject) return;
    const suggestedName = message.generatedProjectName || "nova-project";
    const projectName = window.prompt("Name this project folder:", suggestedName);
    if (projectName === null) return;
    const cleanName = projectName.trim();
    if (!cleanName || /[\\/:*?"<>|]/.test(cleanName) || cleanName === "." || cleanName === "..") {
      alert("Enter a valid folder name without \/ : * ? \" < > or | characters.");
      return;
    }

    const supportsFolderPicker = typeof window !== "undefined" && "showDirectoryPicker" in window;
    if (!supportsFolderPicker) {
      alert("Choosing a folder directly is not supported by this browser. Use Download Project as ZIP and extract it wherever you want.");
      return;
    }
    if (!window.confirm(`Choose a destination folder for \"${cleanName}\" and create ${files.length} file(s) there? Existing files will never be overwritten.`)) return;

    setCreatingProject(true);
    try {
      const picker = (window as Window & { showDirectoryPicker?: (options?: { mode?: string }) => Promise<FileSystemDirectoryHandle> }).showDirectoryPicker;
      if (!picker) throw new Error("Folder selection is not supported in this browser.");
      const destination = await picker({ mode: "readwrite" });
      // Create the project folder only after the user chooses the destination and confirms.
      const projectDir = await destination.getDirectoryHandle(cleanName, { create: true });
      // Preflight all paths before writing anything; refuse to overwrite any existing file.
      const normalized = files.map((file) => {
        const parts = file.path.replace(/\\/g, "/").split("/");
        if (!file.path || file.path.startsWith("/") || parts.some((part) => !part || part === "." || part === "..")) {
          throw new Error(`Unsafe generated file path: ${file.path}`);
        }
        return { ...file, parts };
      });
      for (const file of normalized) {
        let dir = projectDir;
        for (const part of file.parts.slice(0, -1)) dir = await dir.getDirectoryHandle(part, { create: true });
        try {
          await dir.getFileHandle(file.parts[file.parts.length - 1], { create: false });
          throw new Error(`File already exists: ${file.path}. Choose another project folder name; Nova will not overwrite files.`);
        } catch (error) {
          if (error instanceof Error && error.message.startsWith("File already exists:")) throw error;
          // NotFoundError means this file does not exist and can be created safely.
          if (!(error instanceof DOMException) || error.name !== "NotFoundError") throw error;
        }
      }
      const written: Array<{ dir: FileSystemDirectoryHandle; name: string }> = [];
      try {
        for (const file of normalized) {
          let dir = projectDir;
          for (const part of file.parts.slice(0, -1)) dir = await dir.getDirectoryHandle(part, { create: true });
          const name = file.parts[file.parts.length - 1];
          const handle = await dir.getFileHandle(name, { create: true });
          const writable = await handle.createWritable({ keepExistingData: false });
          await writable.write(file.content);
          await writable.close();
          written.push({ dir, name });
        }
      } catch (error) {
        // Roll back files written by this operation if any later write fails.
        for (const file of written.reverse()) {
          try { await file.dir.removeEntry(file.name); } catch { /* best-effort rollback */ }
        }
        throw error;
      }
      setMessages((prev) => [...prev, { role: "assistant", content: `✅ Project saved to your selected folder as \"${cleanName}\".\n\nFiles:\n${files.map((file) => `- ${file.path}`).join("\n")}` }]);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(error instanceof Error ? error.message : "Could not save the project to the selected folder.");
    } finally {
      setCreatingProject(false);
    }
  }

  async function downloadGeneratedProjectZip(message: Message) {
    const files = message.generatedFiles;
    if (!files?.length || creatingProject) return;
    const projectName = (message.generatedProjectName || "nova-project").trim();
    if (!window.confirm(`Download ${files.length} reviewed file(s) as ${projectName}.zip? You can extract it anywhere.`)) return;
    setCreatingProject(true);
    try {
      const response = await fetch(`${BACKEND_URL}/coding/zip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_name: projectName, files }),
      });
      if (!response.ok) {
        let detail = "Could not create the ZIP download.";
        try { const data = await response.json(); detail = data.detail || detail; } catch { /* keep default */ }
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${projectName.replace(/[^a-zA-Z0-9_-]+/g, "-") || "nova-project"}.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setMessages((prev) => [...prev, { role: "assistant", content: `📦 ZIP download started for ${projectName}.zip. Choose any destination in your browser's download settings, then extract the project wherever you want.` }]);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Could not download the project ZIP.");
    } finally {
      setCreatingProject(false);
    }
  }

  // ==========================================================
  // SEND MESSAGE
  // ==========================================================

  async function sendMessage() {
    const message = input.trim();
    if (!message || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setLoading(true);

    try {
      // Coding Mode asks the normal chat endpoint for code in the answer; it never creates project files.
      const chatMessage = codingMode
        ? `Coding Mode is enabled. Answer directly in chat with explanations and fenced code blocks, including the programming language after the opening fence. Do not create project files, return a project-file JSON structure, or save anything to disk.\n\nUser request: ${message}`
        : message;
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: chatMessage, conversation_id: currentConversationId }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || data.error || `Backend returned ${response.status}`);
      }

      if (data.conversation_id) {
        setCurrentConversationId(String(data.conversation_id));
      }

      const answer = data.answer || data.response || "Nova received your message but returned no response.";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: answer,
          intent: codingMode ? "code" : data.intent,
          sources: Array.isArray(data.sources) ? data.sources : [],
        },
      ]);
      speakReply(answer);
      await refreshConversations();
    } catch (error) {
      console.error("Nova backend error:", error);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: error instanceof Error
            ? `I couldn't send your message: ${error.message}`
            : "I couldn't connect to the Nova backend. Make sure FastAPI is running on port 8000.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }


  // ==========================================================

  // ENTER KEY

  // ==========================================================



  function handleKeyDown(

    event: React.KeyboardEvent<HTMLTextAreaElement>

  ) {



    if (

      event.key === "Enter" &&

      !event.shiftKey

    ) {



      event.preventDefault();



      sendMessage();



    }

  }







  // ==========================================================

  // USE PROMPT

  // ==========================================================



  function usePrompt(

    prompt: string

  ) {



    setInput(prompt);



  }





  // ==========================================================

  // OPEN FILE PICKER

  // ==========================================================



  function openFilePicker() {



    if (uploading) {

      return;

    }



    fileInputRef.current?.click();



  }





  // ==========================================================

  // UPLOAD DOCUMENT

  // ==========================================================



  async function uploadDocument(

    event: React.ChangeEvent<HTMLInputElement>

  ) {



    const file =

      event.target.files?.[0];



    if (!file) {

      return;

    }





    // Only PDF

    if (

      !file.name

        .toLowerCase()

        .endsWith(".pdf")

    ) {



      setUploadMessage(

        "Only PDF files are supported."

      );



      return;

    }





    setUploading(true);



    setUploadMessage(

      `Uploading ${file.name}...`

    );





    try {



      const formData =

        new FormData();



      formData.append(

        "file",

        file

      );





      const response =

        await fetch(

          "http://127.0.0.1:8000/upload",

          {

            method: "POST",

            body: formData,

          }

        );





      const data =

        await response.json();





      if (!response.ok || !data.success) {



        throw new Error(

          data.message ||

          "Upload failed."

        );



      }





      setUploadMessage(

        `${data.filename} is ready. ${data.chunks} chunks indexed.`

      );





      // Add system message to chat

      setMessages((prev) => [

        ...prev,

        {

          role: "assistant",

          content:

            `📚 Document ready: ${data.filename}\n\nI indexed ${data.chunks} chunks. You can now ask me questions about this document.`,

        },

      ]);





    } catch (error) {



      console.error(

        "Document upload error:",

        error

      );





      setUploadMessage(

        "Upload failed. Make sure FastAPI is running on port 8000."

      );



    } finally {



      setUploading(false);



      // Reset file input

      if (fileInputRef.current) {



        fileInputRef.current.value = "";



      }



    }

  }





  return (



    <main data-theme={theme} className={`nova-app flex h-screen overflow-hidden ${theme === "dark" ? "bg-black text-white" : "nova-light bg-white text-black"}`}>
      {sidebarOpen && <button type="button" aria-label="Close chat history overlay" onClick={() => setSidebarOpen(false)} className="nova-sidebar-backdrop fixed inset-0 z-30 bg-black/70 md:hidden" />}
      <button type="button" onClick={() => setSidebarOpen((open) => !open)} className="nova-fixed-sidebar-toggle fixed left-3 top-3 z-50 flex h-10 w-10 items-center justify-center rounded-lg border border-white/20 bg-black text-white shadow-lg hover:bg-neutral-800" aria-label={sidebarOpen ? "Close chat history" : "Open chat history"} title={sidebarOpen ? "Close chat history" : "Open chat history"}>{sidebarOpen ? "‹" : "☰"}</button>





      {/* =====================================================

          SIDEBAR

      ====================================================== */}



      <aside className={`nova-sidebar fixed inset-y-0 left-0 z-40 flex w-[min(82vw,330px)] flex-col border-r border-white/10 bg-[#080808] p-4 transition-transform duration-300 md:relative md:z-auto md:w-[330px] md:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:-translate-x-full md:hidden"}`}>



        {/* Logo */}



        <div className="nova-logo mb-8 flex items-center gap-3">



          <div className="nova-mark flex h-10 w-10 items-center justify-center rounded-xl bg-white font-bold text-black">

            N

          </div>



          <div>



            <h1 className="text-lg font-semibold">

              Nova

            </h1>



            <p className="text-xs text-gray-500">

              Local AI

            </p>



          </div>



        </div>





        {/* New Chat */}



        <button

          onClick={newChat}

          className="nova-new-chat mb-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-left text-sm transition hover:bg-white/10"

        >

          + New Chat

        </button>





        {/* Upload */}



        <button

          onClick={openFilePicker}

          disabled={uploading}

          className="mb-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-left text-sm transition hover:bg-white/10 disabled:opacity-50"

        >



          {uploading

            ? "⏳ Uploading..."

            : "📄 Upload PDF"}



        </button>





        {/* Hidden file input */}



        <input

          ref={fileInputRef}

          type="file"

          accept=".pdf,application/pdf"

          onChange={uploadDocument}

          className="hidden"

        />





        {/* Upload status */}



        {uploadMessage && (



          <div className="mb-5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-gray-400">



            {uploadMessage}



          </div>



        )}





        {/* Chats */}



        <div className="flex min-h-0 flex-1 flex-col">



          <p className="mb-3 text-xs uppercase tracking-wider text-gray-600">

            Chats

          </p>





          {conversations.length > 0 ? (
            <div className="nova-chat-history min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain pr-1">
              {conversations.map((conversation) => {
                const title = conversation.title || conversation.first_message || "New Chat";
                const active = currentConversationId === conversation.id;
                return (
                  <div
                    key={conversation.id}
                    className={`group flex items-center gap-1 rounded-lg border px-2 py-1 ${
                      active ? "border-white/15 bg-white/10" : "border-transparent hover:bg-white/5"
                    }`}
                  >
                    <button
                      onClick={() => openConversation(conversation.id)}
                      disabled={loading || Boolean(conversationActionId)}
                      title={title}
                      className="min-w-0 flex-1 truncate py-2 text-left text-sm text-gray-300 disabled:opacity-50"
                    >
                      {title}
                    </button>
                    <button
                      onClick={() => renameChat(conversation)}
                      disabled={loading || Boolean(conversationActionId)}
                      title="Rename chat"
                      aria-label={`Rename ${title}`}
                      className="rounded px-1.5 py-1 text-xs text-gray-500 hover:bg-white/10 hover:text-white disabled:opacity-30"
                    >
                      ✎
                    </button>
                    <button
                      onClick={() => deleteChat(conversation)}
                      disabled={loading || Boolean(conversationActionId)}
                      title="Delete chat"
                      aria-label={`Delete ${title}`}
                      className="rounded px-1.5 py-1 text-xs text-gray-500 hover:bg-red-500/20 hover:text-red-300 disabled:opacity-30"
                    >
                      ×
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="px-3 text-sm text-gray-600">
              No conversations yet
            </p>
          )}



        </div>





        {/* Settings */}



        <div className="border-t border-white/10 pt-4">



          <div className="text-sm text-gray-400">

            ⚙ Settings

          </div>



          <div className="mt-2 text-xs text-gray-600">

            Ollama • Llama 3

          </div>



          <div className="mt-1 text-xs text-gray-700">

            RAG • SQLite Memory

          </div>



        </div>



      </aside>





      {/* =====================================================

          MAIN AREA

      ====================================================== */}



      <section className="flex min-w-0 flex-1 flex-col">





        {/* Header */}



        <header className="nova-header flex h-16 items-center justify-between border-b border-white/10 px-5">



          <div>



            <h2 className="font-semibold">

              Nova

            </h2>



            <p className="text-xs text-gray-500">

              Local AI Assistant

            </p>



          </div>





          <div className="flex items-center gap-3 text-xs text-gray-500">
            <button
              type="button"
              onClick={toggleTheme}
              className="nova-theme-toggle rounded-lg border border-white/10 px-3 py-2 text-xs transition hover:border-white/40 hover:text-white"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? "☀ Light" : "☾ Dark"}
            </button>
            <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-green-500" />



            Local</span>
          </div>



        </header>





        {/* =================================================

            CHAT AREA

        ================================================== */}



        <div className="flex-1 overflow-y-auto">



          {messages.length === 0 ? (



            <div className="flex h-full items-center justify-center px-6">



              <div className="w-full max-w-2xl text-center">



                <div className="nova-welcome-mark mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-white text-2xl font-bold text-black">

                  N

                </div>





                <h1 className="nova-welcome-title text-3xl font-semibold">

                  Welcome to Nova

                </h1>





                <p className="mt-3 text-gray-500">

                  Your private local AI assistant.

                </p>





                <div className="mt-8 grid gap-3 sm:grid-cols-3">





                  <button

                    onClick={() =>

                      usePrompt(

                        "What can you help me with?"

                      )

                    }

                    className="nova-suggestion rounded-xl border border-white/10 bg-white/5 p-4 text-left text-sm text-gray-400 transition hover:bg-white/10"

                  >

                    <span className="nova-suggestion-icon" aria-hidden="true">✨</span>
                    <span>What can you help me with?</span>

                  </button>





                  <button

                    onClick={() =>

                      usePrompt(

                        "What are the types of machine learning according to my notes?"

                      )

                    }

                    className="nova-suggestion rounded-xl border border-white/10 bg-white/5 p-4 text-left text-sm text-gray-400 transition hover:bg-white/10"

                  >

                    <span className="nova-suggestion-icon" aria-hidden="true">📚</span>
                    <span>Ask about my notes</span>

                  </button>





                  <button

                    onClick={() =>

                      openFilePicker()

                    }

                    className="nova-suggestion rounded-xl border border-white/10 bg-white/5 p-4 text-left text-sm text-gray-400 transition hover:bg-white/10"

                  >

                    <span className="nova-suggestion-icon" aria-hidden="true">📄</span>
                    <span>Upload a PDF</span>

                  </button>



                </div>



              </div>



            </div>



          ) : (



            <div className="mx-auto w-full max-w-3xl space-y-6 px-5 py-8">





              {messages.map(

                (

                  message,

                  index

                ) => (



                  <div

                    key={index}

                    className={`flex gap-3 ${

                      message.role === "user"

                        ? "justify-end"

                        : "justify-start"

                    }`}

                  >





                    {message.role ===

                      "assistant" && (



                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-xs font-bold text-black">

                        N

                      </div>



                    )}





                    <div

                      className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${

                        message.role === "user"

                          ? "bg-white text-black"

                          : "border border-white/10 bg-white/5 text-gray-200"

                      }`}

                    >



                      {renderMessageContent(message.content)}
                      {message.role === "assistant" &&
                        message.sources &&
                        message.sources.length > 0 && (
                          <div className="mt-4 border-t border-white/10 pt-3">
                            <p className="mb-2 text-xs font-medium text-gray-500">
                              {message.intent === "rag"
                                ? "Sources from your documents"
                                : "Web sources"}
                            </p>

                            <div className="space-y-2">
                              {message.sources.map((source, sourceIndex) => {
                                const sourceTitle =
                                  typeof source === "string"
                                    ? source
                                    : source.title || source.url || "Source";

                                const sourceUrl =
                                  typeof source === "string"
                                    ? ""
                                    : source.url || "";

                                return sourceUrl ? (
                                  <a
                                    key={sourceIndex}
                                    href={sourceUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="block rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-gray-400 transition hover:bg-white/10 hover:text-white"
                                  >
                                    <span className="mr-2">↗</span>
                                    {sourceTitle}
                                  </a>
                                ) : (
                                  <div
                                    key={sourceIndex}
                                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-gray-400"
                                  >
                                    📄 {sourceTitle}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                    </div>



                  </div>



                )

              )}





              {loading && (



                <div className="flex gap-3">



                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-xs font-bold text-black">

                    N

                  </div>



                  <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-gray-500">

                    Nova is thinking...

                  </div>



                </div>



              )}



            </div>



          )}



        </div>





        {/* =================================================

            INPUT AREA

        ================================================== */}



        <div className="border-t border-white/10 p-4">



          <div className="nova-composer mx-auto flex max-w-3xl items-end gap-3 rounded-2xl border border-white/10 bg-[#111111] p-2">





            {/* Mobile upload button */}



            <button

              onClick={openFilePicker}

              disabled={uploading}

              title="Upload PDF"

              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-gray-400 transition hover:bg-white/10 hover:text-white disabled:opacity-30"

            >

              📎

            </button>





            <button
              type="button"
              onClick={() => setCodingMode((enabled) => !enabled)}
              disabled={loading}
              title={codingMode ? "Switch to normal chat" : "Switch to Coding Mode"}
              aria-pressed={codingMode}
              className={`flex h-10 shrink-0 items-center justify-center rounded-xl border px-2 text-xs font-medium transition disabled:opacity-30 ${codingMode ? "border-white/50 bg-white/15 text-white" : "border-white/10 text-gray-400 hover:bg-white/10 hover:text-white"}`}
            >
              {codingMode ? "</> Coding" : "</> Code"}
            </button>

            <textarea
              value={input}

              onChange={(event) =>

                setInput(

                  event.target.value

                )

              }

              onKeyDown={handleKeyDown}

              placeholder={codingMode ? "Ask for code, an explanation, or debugging help..." : "Message Nova... or record your voice offline"}

              rows={1}

              disabled={loading}

              className="nova-textarea max-h-32 min-h-12 flex-1 resize-none bg-transparent px-3 py-3 text-sm text-white outline-none placeholder:text-gray-600 disabled:opacity-50"

            />





            <button
              onClick={toggleListening}
              disabled={loading}
              title={isListening ? "Stop voice input" : "Speak in English (India)"}
              aria-label={isListening ? "Stop voice input" : "Start voice input"}
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition disabled:opacity-30 ${
                isListening ? "border-white/60 bg-white/15 text-white" : "border-white/10 text-gray-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              {isListening ? "■" : "🎙️"}
            </button>

            <button
              onClick={() => {
                if (voiceRepliesEnabled) stopSpeaking();
                setVoiceRepliesEnabled((enabled) => !enabled);
                setVoiceStatus(voiceRepliesEnabled ? "Spoken replies turned off." : "Spoken replies turned on (English, India).");
              }}
              title={voiceRepliesEnabled ? "Turn spoken replies off" : "Turn spoken replies on"}
              aria-label={voiceRepliesEnabled ? "Turn spoken replies off" : "Turn spoken replies on"}
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition ${
                voiceRepliesEnabled ? "border-white/10 text-gray-300 hover:bg-white/10 hover:text-white" : "border-white/10 text-gray-600 hover:bg-white/10 hover:text-white"
              }`}
            >
              {voiceRepliesEnabled ? "🔊" : "🔇"}
            </button>

            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              title="Send message"
              aria-label="Send message"
              className="nova-send flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-black transition hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-30"
            >
              ↑
            </button>



          </div>





          {voiceStatus && (
            <p aria-live="polite" className={`mt-2 text-center text-xs ${isListening ? "text-white" : "text-gray-500"}`}>
              {voiceStatus}
            </p>
          )}

          <p className="mt-2 text-center text-xs text-gray-700">
            Nova runs locally using Ollama. Voice: English (India).
          </p>



        </div>



      </section>



      <style jsx global>{`
        /* Nova monochrome theme */
        .nova-app { background: #000 !important; color: #f5f5f5; }
        .nova-app.nova-light { background: #fff !important; color: #111 !important; }
        .nova-app aside { background: #050505 !important; border-color: #262626 !important; }
        .nova-app .nova-mark, .nova-app .nova-welcome-mark { background: #fff !important; color: #000 !important; border-radius: 15px; box-shadow: none; }
        .nova-app .nova-header { background: #000 !important; border-color: #262626 !important; }
        .nova-app .nova-theme-toggle { border-color: #333 !important; color: #ddd !important; }
        .nova-app aside .nova-new-chat { background: #fff !important; border-color: #fff !important; color: #000 !important; font-weight: 650; box-shadow: none; }
        .nova-app aside .nova-new-chat:hover { background: #e5e5e5 !important; }
        .nova-app aside .group button { background: transparent !important; color: #ddd !important; border-color: transparent !important; }
        .nova-app aside .group button:hover { background: #1a1a1a !important; color: #fff !important; }
        .nova-app aside .group { background: transparent; }
        .nova-app aside .group button:first-of-type { background: transparent !important; color: #ddd !important; }
        .nova-app .nova-suggestion { min-height: 178px; display: flex; flex-direction: column; align-items: flex-start; justify-content: flex-start; gap: 12px; position: relative; overflow: hidden; border-radius: 24px; border-color: #383838 !important; background: linear-gradient(145deg, #1c1c1c, #141414) !important; color: #f0f0f0 !important; padding: 22px !important; }
        .nova-app .nova-suggestion::before { content: none !important; display: none !important; }
        .nova-app .nova-suggestion-icon { display: flex; align-items: center; justify-content: center; width: 50px; height: 50px; flex: 0 0 50px; border-radius: 14px; background: #303030; box-shadow: inset 0 0 0 1px #444; font-size: 27px; line-height: 1; }
        .nova-app .nova-suggestion > span:last-child { color: #f0f0f0; font-weight: 500; }
        .nova-app .nova-suggestion:hover { transform: translateY(-3px); border-color: #666 !important; background: linear-gradient(145deg, #242424, #191919) !important; box-shadow: 0 8px 26px rgba(255,255,255,.04); }
        .nova-app .nova-composer { border-color: #777 !important; border-radius: 26px !important; background: #050505 !important; box-shadow: none; padding: 12px !important; }
        .nova-app .nova-composer:focus-within { border-color: #aaa !important; box-shadow: 0 0 0 2px rgba(255,255,255,.05); }
        .nova-app .nova-send:not(:disabled) { background: #fff !important; color: #000 !important; border-radius: 15px; }
        .nova-app .nova-send:hover:not(:disabled) { background: #ddd !important; box-shadow: none; }
        .nova-app .nova-textarea { color: #f5f5f5 !important; }
        .nova-app .nova-textarea::placeholder { color: #777 !important; }
        .nova-app .nova-logo { margin-bottom: 28px; }
        .nova-app .nova-welcome-mark { animation: novaFadeUp .7s ease-out both, novaOrbitFloat 3.2s ease-in-out 800ms infinite; }
        .nova-app .nova-welcome-title { font-size: clamp(2rem, 3vw, 2.7rem); letter-spacing: -.035em; }
        .nova-app .nova-welcome-title::first-line { color: #f7f7f7; }
        .nova-app .nova-suggestion { transition: transform .22s ease, border-color .22s ease, background-color .22s ease, box-shadow .22s ease; }
        .nova-app .nova-theme-toggle:hover { color: #fff !important; border-color: #777 !important; }
        .nova-sidebar-backdrop { backdrop-filter: blur(2px); }
        .nova-fixed-sidebar-toggle { transition: background-color .18s ease, color .18s ease, border-color .18s ease; }
        .nova-light .nova-fixed-sidebar-toggle { background: #fff !important; color: #111 !important; border-color: #ccc !important; }
        .nova-light .nova-fixed-sidebar-toggle:hover { background: #eee !important; }
        @media (min-width: 768px) {
          .nova-app:has(.nova-sidebar.translate-x-0) .nova-fixed-sidebar-toggle { left: 292px; }
        }

        .nova-sidebar-toggle { background: #050505; }
        .nova-sidebar-toggle:hover { background: #1b1b1b !important; }
        .nova-light .nova-sidebar-toggle { background: #fff !important; color: #222 !important; border-color: #ccc !important; }
        .nova-light .nova-sidebar-toggle:hover { background: #eee !important; }

        .nova-chat-history { max-height: 100%; scrollbar-width: thin; scrollbar-color: #555 #080808; }
        .nova-chat-history::-webkit-scrollbar { width: 7px; }
        .nova-chat-history::-webkit-scrollbar-track { background: #080808; }
        .nova-chat-history::-webkit-scrollbar-thumb { background: #555; border-radius: 8px; }
        .nova-chat-history::-webkit-scrollbar-thumb:hover { background: #888; }
        .nova-code-block { background: #080808 !important; }
        .nova-code-block button:hover { border-color: #777 !important; color: #fff !important; }
        @keyframes novaOrbitFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }
        .nova-light { background: #f8f8f8 !important; color: #111 !important; }
        .nova-light aside { background: #f1f1f1 !important; }
        .nova-light .nova-composer { background: #fff !important; }
        .nova-light .nova-textarea { color: #111 !important; }
        .nova-light .nova-header { background: #fff !important; }
        .nova-light .nova-sidebar { background: #f5f5f5 !important; }
        .nova-light .nova-composer { background: #fff !important; }
        .nova-light .nova-suggestion { background: #fff !important; color: #333 !important; }
        .nova-light .nova-send:not(:disabled) { background: #111 !important; color: #fff !important; }
        .nova-light .nova-new-chat { background: #111 !important; color: #fff !important; border-color: #111 !important; }
        .nova-light .nova-welcome-mark, .nova-light .nova-mark { background: #111 !important; color: #fff !important; }
        .nova-light .nova-sidebar .group button { color: #333 !important; }
        .nova-light .nova-sidebar .group button:hover { background: #e5e5e5 !important; color: #111 !important; }
        .nova-app { transition: background-color .25s ease, color .25s ease; }
        .nova-logo { animation: novaFadeUp .55s ease both; }
        .nova-mark, .nova-welcome-mark { transition: box-shadow .25s ease, transform .25s ease; }
        .nova-mark:hover, .nova-welcome-mark:hover { transform: translateY(-2px); box-shadow: none; }
        .nova-welcome-title { animation: novaFadeUp .65s .08s ease both; }
        .nova-composer { transition: border-color .2s ease, box-shadow .2s ease, background-color .25s ease; }
        .nova-send:hover:not(:disabled) { transform: translateY(-1px) scale(1.04); box-shadow: none; }
        .nova-theme-toggle:hover { transform: translateY(-1px); }
        .nova-app button { transition-property: color, background-color, border-color, box-shadow, transform; transition-duration: .18s; }
        .nova-light aside { background: #f1f1f1 !important; color: #111 !important; border-color: #ddd !important; }
        .nova-light aside button, .nova-light aside h1, .nova-light aside p, .nova-light aside div { color: #333; }
        .nova-light aside button { border-color: #ddd; }
        .nova-light .nova-header, .nova-light .border-t { border-color: #ddd !important; }
        .nova-light .nova-header p, .nova-light .nova-header .text-gray-500 { color: #666 !important; }
        .nova-light .nova-header h2, .nova-light .nova-welcome-title { color: #111 !important; }
        .nova-light .nova-theme-toggle { color: #333; border-color: #ccc; }
        .nova-light .nova-suggestion { background: #fff !important; color: #444 !important; border-color: #ddd !important; }
        .nova-light .nova-suggestion:hover { border-color: #888 !important; background: #fafafa !important; }
        .nova-light .nova-composer { background: #fff !important; border-color: #ccc !important; }
        .nova-light .nova-textarea { color: #111 !important; }
        .nova-light .nova-header { background: #fff !important; }
        .nova-light .nova-sidebar { background: #f5f5f5 !important; }
        .nova-light .nova-composer { background: #fff !important; }
        .nova-light .nova-suggestion { background: #fff !important; color: #333 !important; }
        .nova-light .nova-send:not(:disabled) { background: #111 !important; color: #fff !important; }
        .nova-light .nova-new-chat { background: #111 !important; color: #fff !important; border-color: #111 !important; }
        .nova-light .nova-welcome-mark, .nova-light .nova-mark { background: #111 !important; color: #fff !important; }
        .nova-light .nova-sidebar .group button { color: #333 !important; }
        .nova-light .nova-sidebar .group button:hover { background: #e5e5e5 !important; color: #111 !important; }
        .nova-light .nova-textarea::placeholder { color: #888 !important; }
        .nova-light .nova-app, .nova-light main { color: #111; }
        .nova-light .text-gray-200, .nova-light .text-gray-300, .nova-light .text-gray-400 { color: #444; }
        .nova-light .bg-white\/5 { background: #fff; }

        /* Complete light theme: readable text and light surfaces throughout */
        .nova-app.nova-light { background: #ffffff !important; color: #171717 !important; }
        .nova-light .nova-header { background: #ffffff !important; border-color: #dedede !important; }
        .nova-light .nova-sidebar { background: #f7f7f7 !important; color: #171717 !important; border-color: #dedede !important; }
        .nova-light .nova-sidebar .nova-logo h1,
        .nova-light .nova-sidebar .nova-logo p,
        .nova-light .nova-sidebar .text-gray-300,
        .nova-light .nova-sidebar .text-gray-400,
        .nova-light .nova-sidebar .text-gray-500 { color: #444444 !important; }
        .nova-light .nova-sidebar .nova-new-chat { background: #171717 !important; color: #ffffff !important; border-color: #171717 !important; }
        .nova-light .nova-sidebar .nova-new-chat:hover { background: #333333 !important; }
        .nova-light .nova-sidebar .group { background: transparent !important; border-color: transparent !important; }
        .nova-light .nova-sidebar .group:hover { background: #e9e9e9 !important; }
        .nova-light .nova-sidebar .group button,
        .nova-light .nova-sidebar .group button:first-of-type { background: transparent !important; color: #333333 !important; }
        .nova-light .nova-sidebar .group button:hover { background: #e5e5e5 !important; color: #111111 !important; }
        .nova-light .nova-sidebar .group button[title="Rename chat"],
        .nova-light .nova-sidebar .group button[title="Delete chat"] { color: #555555 !important; }
        .nova-light .nova-sidebar .group button[title="Rename chat"]:hover,
        .nova-light .nova-sidebar .group button[title="Delete chat"]:hover { color: #111111 !important; }
        .nova-light .nova-sidebar button:not(.nova-new-chat) { border-color: #dedede; }
        .nova-light .nova-sidebar .border-t { border-color: #dedede !important; }
        .nova-light .nova-header h2,
        .nova-light .nova-welcome-title { color: #111111 !important; }
        .nova-light .nova-header p,
        .nova-light .nova-header .text-gray-500 { color: #666666 !important; }
        .nova-light .nova-theme-toggle { background: #ffffff !important; color: #222222 !important; border-color: #cccccc !important; }
        .nova-light .nova-theme-toggle:hover { background: #f0f0f0 !important; color: #111111 !important; border-color: #888888 !important; }
        .nova-light .nova-welcome-mark,
        .nova-light .nova-mark { background: #111111 !important; color: #ffffff !important; }
        .nova-light .nova-suggestion { background: #ffffff !important; color: #333333 !important; border-color: #dddddd !important; }
        .nova-light .nova-suggestion::before { display: none !important; }
        .nova-light .nova-suggestion-icon { background: #e7e7e7 !important; box-shadow: inset 0 0 0 1px #d2d2d2 !important; }
        .nova-light .nova-suggestion > span:last-child { color: #333333 !important; }
        .nova-light .nova-suggestion:hover { background: #f8f8f8 !important; border-color: #999999 !important; box-shadow: 0 8px 24px rgba(0,0,0,.05) !important; }
        .nova-light .nova-composer { background: #ffffff !important; border-color: #cccccc !important; box-shadow: none !important; }
        .nova-light .nova-composer:focus-within { border-color: #888888 !important; box-shadow: 0 0 0 2px rgba(0,0,0,.05) !important; }
        .nova-light .nova-textarea { color: #111111 !important; }
        .nova-light .nova-textarea::placeholder { color: #777777 !important; }
        .nova-light .nova-send:not(:disabled) { background: #111111 !important; color: #ffffff !important; }
        .nova-light .nova-send:hover:not(:disabled) { background: #333333 !important; }
        .nova-light .text-gray-200,
        .nova-light .text-gray-300,
        .nova-light .text-gray-400 { color: #333333 !important; }
        .nova-light .text-gray-500,
        .nova-light .text-gray-600,
        .nova-light .text-gray-700 { color: #666666 !important; }
        .nova-light .bg-white\\/5 { background: #f7f7f7 !important; }
        .nova-light .border-white\\/10 { border-color: #dddddd !important; }
        .nova-light .bg-black\\/20 { background: #f5f5f5 !important; }
        .nova-light .nova-code-block { background: #f7f7f7 !important; color: #171717 !important; border-color: #dddddd !important; }
        .nova-light .nova-code-block > div { background: #eeeeee !important; border-color: #dddddd !important; }
        .nova-light .nova-code-block span { color: #444444 !important; }
        .nova-light .nova-code-block pre { color: #171717 !important; }
        .nova-light .nova-code-block code { color: #171717 !important; }
        .nova-light .nova-code-block button { color: #333333 !important; border-color: #cccccc !important; }
        .nova-light .nova-code-block button:hover { color: #111111 !important; border-color: #888888 !important; }
        .nova-light .nova-sidebar .nova-chat-history { scrollbar-color: #aaaaaa #eeeeee; }
        .nova-light .nova-chat-history::-webkit-scrollbar-track { background: #eeeeee; }
        .nova-light .nova-chat-history::-webkit-scrollbar-thumb { background: #aaaaaa; }
        .nova-light .nova-chat-history::-webkit-scrollbar-thumb:hover { background: #777777; }

                @keyframes novaFadeUp { from { opacity: 0; transform: translateY(9px); } to { opacity: 1; transform: translateY(0); } }
        @media (prefers-reduced-motion: reduce) { .nova-app *, .nova-app *::before, .nova-app *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; scroll-behavior: auto !important; } }
      `}</style>
    </main>

  );

}