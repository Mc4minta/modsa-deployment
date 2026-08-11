export type Lang = "en" | "th";

const locales: Record<Lang, Record<string, string>> = {
  en: {
    // Sidebar
    appName: "MOD-SA",
    appTagline: "KMUTT Student Affairs Assistant",
    newChat: "New Chat",
    chatHistory: "Chat History",
    faq: "FAQ",
    announcements: "Announcements",
    settings: "Settings",
    noHistory: "No conversations yet",
    deleteChat: "Delete",
    clearHistory: "Clear history",
    today: "Today",
    yesterday: "Yesterday",
    older: "Older",

    // Welcome
    welcomeTitle: "Hello! I'm MOD-SA 👋",
    welcomeSubtitle:
      "Your AI assistant for KMUTT Student Affairs. Ask me anything about admissions, registration, tuition, scholarships, and more.",
    welcomeHint: "Choose a topic below or type your question",

    // Starter Questions
    starterAdmissionsTitle: "Admissions",
    starterAdmissionsQ: "How do I apply to KMUTT?",
    starterRegistrationTitle: "Registration",
    starterRegistrationQ: "How to register for courses?",
    starterTuitionTitle: "Tuition Fees",
    starterTuitionQ: "What are the tuition fee payment deadlines?",
    starterScholarshipsTitle: "Scholarships",
    starterScholarshipsQ: "What scholarships are available for new students?",
    starterCalendarTitle: "Academic Calendar",
    starterCalendarQ: "When does the semester start and end?",

    // Chat
    inputPlaceholder: "Ask MOD-SA anything about student affairs...",
    send: "Send",
    stop: "Stop",
    copied: "Copied!",
    copyMessage: "Copy",
    thinking: "MOD-SA is thinking",
    errorMessage: "Sorry, something went wrong. Please try again.",
    retryMessage: "Retry",
    requestStopped: "Request stopped.",

    // Sources
    sources: "Sources",
    viewSource: "View Source",
    viewDocument: "View Document",
    snippetsUsed: "Retrieved snippets",
    page: "Page",
    department: "Department",
    noSources: "No sources available",
    evidenceCoverage: "Evidence coverage",
    evidenceDisclaimer:
      "Sources show retrieved evidence; they do not guarantee that every answer is correct.",
    sourceUnit: "source",
    sourcesUnit: "sources",
    opensNewTab: "opens in new tab",

    // Input
    voiceInput: "Voice input",
    recording: "Recording...",
    charCount: "characters",
    questionRequired: "Enter a question before sending.",
    questionTooLong: "Questions must be 1,500 characters or fewer.",
    sensitiveInput:
      "For your safety, do not include passwords, API keys, national ID numbers, or other sensitive personal data.",
    invalidQuestion: "Please check your question and try again.",
    voiceNotSupported: "Voice input is not supported by this browser.",
    voicePermissionDenied: "Microphone access was denied. Allow it in your browser settings to use voice input.",
    newResponse: "New response",
    storageWarning: "Chat history could not be saved.",
    skipToInput: "Skip to message input",

    // Announcements
    announcementsTitle: "Announcements",
    noAnnouncements: "No announcements at this time.",

    // Settings
    settingsTitle: "Settings",
    language: "Language",

    // General
    close: "Close",
    cancel: "Cancel",
    confirm: "Confirm",
    loading: "Loading...",
    poweredBy: "Powered by KMUTT Student Affairs",
  },

  th: {
    clearHistory: "ล้างประวัติแชท",
    requestStopped: "หยุดคำขอแล้ว",
    evidenceCoverage: "ความครอบคลุมของหลักฐาน",
    evidenceDisclaimer:
      "แหล่งข้อมูลแสดงหลักฐานที่ค้นพบ แต่ไม่ได้รับประกันว่าคำตอบถูกต้องเสมอไป",
    storageWarning: "ไม่สามารถบันทึกประวัติการสนทนาได้",
    // Sidebar
    appName: "MOD-SA",
    appTagline: "ผู้ช่วย AI กิจการนักศึกษา มจธ.",
    newChat: "แชทใหม่",
    chatHistory: "ประวัติแชท",
    faq: "คำถามที่พบบ่อย",
    announcements: "ประกาศ",
    settings: "ตั้งค่า",
    noHistory: "ยังไม่มีบทสนทนา",
    deleteChat: "ลบ",
    today: "วันนี้",
    yesterday: "เมื่อวาน",
    older: "ก่อนหน้า",

    // Welcome
    welcomeTitle: "สวัสดี! ฉันคือ MOD-SA 👋",
    welcomeSubtitle:
      "ผู้ช่วย AI สำหรับกิจการนักศึกษา มจธ. ถามได้ทุกเรื่องเกี่ยวกับการรับสมัคร ลงทะเบียน ค่าเล่าเรียน ทุนการศึกษา และอื่นๆ",
    welcomeHint: "เลือกหัวข้อด้านล่าง หรือพิมพ์คำถามของคุณ",

    // Starter Questions
    starterAdmissionsTitle: "การรับสมัคร",
    starterAdmissionsQ: "สมัครเรียนที่ มจธ. ต้องทำอย่างไร?",
    starterRegistrationTitle: "การลงทะเบียน",
    starterRegistrationQ: "ลงทะเบียนเรียนอย่างไร?",
    starterTuitionTitle: "ค่าเล่าเรียน",
    starterTuitionQ: "กำหนดชำระค่าเล่าเรียนเมื่อไร?",
    starterScholarshipsTitle: "ทุนการศึกษา",
    starterScholarshipsQ: "มีทุนการศึกษาอะไรบ้างสำหรับนักศึกษาใหม่?",
    starterCalendarTitle: "ปฏิทินการศึกษา",
    starterCalendarQ: "เทอมเริ่มและสิ้นสุดเมื่อไร?",

    // Chat
    inputPlaceholder: "ถาม MOD-SA เกี่ยวกับกิจการนักศึกษา...",
    send: "ส่ง",
    stop: "หยุด",
    copied: "คัดลอกแล้ว!",
    copyMessage: "คัดลอก",
    thinking: "MOD-SA กำลังคิด",
    errorMessage: "ขออภัย เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง",
    retryMessage: "ลองใหม่",

    // Sources
    sources: "แหล่งข้อมูล",
    viewSource: "ดูแหล่งข้อมูล",
    viewDocument: "ดูเอกสาร",
    snippetsUsed: "ข้อมูลที่ดึงมา",
    page: "หน้า",
    department: "หน่วยงาน",
    noSources: "ไม่มีแหล่งข้อมูล",
    sourceUnit: "แหล่งข้อมูล",
    sourcesUnit: "แหล่งข้อมูล",
    opensNewTab: "เปิดในแท็บใหม่",

    // Input
    voiceInput: "อินพุตด้วยเสียง",
    recording: "กำลังบันทึก...",
    charCount: "ตัวอักษร",
    questionRequired: "กรุณาพิมพ์คำถามก่อนส่ง",
    questionTooLong: "คำถามต้องมีความยาวไม่เกิน 1,500 ตัวอักษร",
    sensitiveInput:
      "เพื่อความปลอดภัย กรุณาอย่าใส่รหัสผ่าน API key เลขบัตรประชาชน หรือข้อมูลส่วนบุคคลที่ละเอียดอ่อน",
    invalidQuestion: "กรุณาตรวจสอบคำถามแล้วลองอีกครั้ง",
    voiceNotSupported: "เบราว์เซอร์นี้ไม่รองรับการรับเสียง",
    voicePermissionDenied: "ไม่ได้รับอนุญาตให้ใช้ไมโครโฟน กรุณาอนุญาตในการตั้งค่าเบราว์เซอร์เพื่อใช้อินพุตด้วยเสียง",
    newResponse: "มีคำตอบใหม่",
    skipToInput: "ข้ามไปยังช่องพิมพ์ข้อความ",

    // Announcements
    announcementsTitle: "ประกาศ",
    noAnnouncements: "ไม่มีประกาศในขณะนี้",

    // Settings
    settingsTitle: "ตั้งค่า",
    language: "ภาษา",

    // General
    close: "ปิด",
    cancel: "ยกเลิก",
    confirm: "ยืนยัน",
    loading: "กำลังโหลด...",
    poweredBy: "ขับเคลื่อนโดย กิจการนักศึกษา มจธ.",
  },
};

export default locales;
