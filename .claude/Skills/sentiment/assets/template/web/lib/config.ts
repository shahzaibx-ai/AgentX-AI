/** Branding and placeholder user. Change these to rebrand the app. */
export const APP_CONFIG = {
  appName: "Sentiment Studio",
  appDescription: "Sentiment analysis with PyTorch and Hugging Face Transformers.",
  user: { name: "Rizwan" },
} as const;

/** Example texts per model domain, shown as one-click samples. */
export const EXAMPLES: Record<string, { name: string; text: string }[]> = {
  Financial: [
    {
      name: "Earnings beat",
      text: "Revenue rose 18% year over year and the company raised its full-year guidance.",
    },
    {
      name: "Profit warning",
      text: "Shares fell sharply after the bank reported a loss and cut its dividend.",
    },
    {
      name: "Neutral filing",
      text: "The board will hold its annual general meeting in Frankfurt on 14 May.",
    },
  ],
  "Social media": [
    { name: "Happy post", text: "@rizwan just tried the new update and it's so smooth 😍 https://t.co/x" },
    { name: "Complaint", text: "Third day without internet and support keeps hanging up on me." },
    { name: "Neutral", text: "Live stream starts at 7pm tonight, link in bio." },
  ],
  "Product reviews": [
    { name: "5-star review", text: "Excellent headphones, the battery lasts all week. Highly recommended!" },
    { name: "Mixed review", text: "Good sound, but the case feels cheap and the app is confusing." },
    { name: "Avis en français", text: "Produit de mauvaise qualité, il s'est cassé après deux jours." },
  ],
  Topic: [
    {
      name: "Glowing review",
      text: "The battery life is fantastic and setup took two minutes. Honestly the best headphones I've owned.",
    },
    { name: "Complaint", text: "Support never replied and the replacement arrived broken." },
    {
      name: "Mixed",
      text: "The hotel room was clean and the staff were friendly, but the wifi was slow and breakfast was cold.",
    },
    { name: "Negation", text: "The movie wasn't bad at all, though the ending felt rushed." },
  ],
};

export const BATCH_SAMPLE = [
  "Delivery was fast and the packaging was perfect.",
  "The app keeps crashing every time I open the camera.",
  "It's okay. Does what it says, nothing more.",
  "Absolutely love the new update, the dark mode is beautiful!",
  "Customer service was rude and unhelpful.",
  "Not worth the price, the quality is poor.",
  "Great food, but the waiter forgot our drinks twice.",
  "I would definitely recommend this course to a friend.",
].join("\n");
