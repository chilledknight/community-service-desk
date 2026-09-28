// Community Service Desk - Minimal Accessible JS
document.addEventListener("DOMContentLoaded", () => {
  // Dismiss flash alerts
  document.querySelectorAll(".alert-dismiss").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const alert = e.target.closest(".alert");
      if (alert) alert.remove();
    });
  });

  // Switch reply tab in ticket detail between Public Reply and Internal Note
  const publicTab = document.getElementById("tab-public-reply");
  const noteTab = document.getElementById("tab-internal-note");
  const entryTypeInput = document.getElementById("input-entry-type");
  const replySubmitBtn = document.getElementById("btn-submit-reply");
  const noteHelpText = document.getElementById("note-help-text");

  if (publicTab && noteTab && entryTypeInput) {
    publicTab.addEventListener("click", () => {
      publicTab.classList.add("active", "btn-primary");
      publicTab.classList.remove("btn-secondary");
      noteTab.classList.remove("active", "btn-primary");
      noteTab.classList.add("btn-secondary");
      entryTypeInput.value = "REQUESTER_VISIBLE_REPLY";
      if (replySubmitBtn) {
        replySubmitBtn.textContent = "Send Public Reply";
        replySubmitBtn.classList.remove("btn-warning");
        replySubmitBtn.classList.add("btn-primary");
      }
      if (noteHelpText) noteHelpText.style.display = "none";
    });

    noteTab.addEventListener("click", () => {
      noteTab.classList.add("active", "btn-primary");
      noteTab.classList.remove("btn-secondary");
      publicTab.classList.remove("active", "btn-primary");
      publicTab.classList.add("btn-secondary");
      entryTypeInput.value = "INTERNAL_NOTE";
      if (replySubmitBtn) {
        replySubmitBtn.textContent = "Add Internal Note (Staff Only)";
        replySubmitBtn.classList.remove("btn-primary");
        replySubmitBtn.classList.add("btn-warning");
      }
      if (noteHelpText) noteHelpText.style.display = "block";
    });
  }
});
