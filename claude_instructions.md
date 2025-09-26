# Claude Apply Instructions

Please follow these instructions **every time you apply changes**:

---

## 🖥️ Webserver Environment

- Assume there is a **webserver running** at:  
  `http://localhost:8000`
- You don't need to start a webserver for your own testing, assume it's already running.
- You are encouraged to **use `curl` to fetch and inspect the output** of the server.
- Always **parse and interpret the returned HTML** to validate whether your changes have the desired effect.

---

## 🎨 CSS & JS Awareness

- When making **CSS changes**, remember:
  - There may be **JavaScript that interacts with the DOM**.
  - Consider dynamic states, classes, or styles that may be applied via JS.
  - Do **not assume static HTML** — the final appearance may depend on JS execution.

---

## ✅ Validation Checklist

Before finalizing any apply:

- [ ] Did you curl `http://localhost:8000` to confirm changes in the output?
- [ ] Did you examine the HTML response for structural or visual validation?
- [ ] If CSS was changed, did you consider any JavaScript-related effects?

---

Thanks! Stick to this on every apply for best results.
