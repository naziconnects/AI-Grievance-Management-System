document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("grievanceForm");
  if (form) {
    form.addEventListener("submit", (event) => {
      const description = form.querySelector('[name="description"]');
      if (description && description.value.trim().length < 15) {
        event.preventDefault();
        description.setCustomValidity("Please provide at least 15 characters so the concern can be reviewed.");
        description.reportValidity();
      } else if (description) {
        description.setCustomValidity("");
      }
    });
  }
  document.querySelectorAll("input[type=file]").forEach((input) => {
    input.addEventListener("change", () => {
      const file = input.files[0];
      if (file && file.size > 5 * 1024 * 1024) {
        alert("File must be 5 MB or smaller.");
        input.value = "";
      }
    });
  });
});