# Word influence (integrated gradients)

`api/app/ml/explain.py`. It runs for `POST /predict` when `explain` is true and
`EXPLAIN_STEPS > 0`.

## What is attributed

The prediction's **expected polarity**: `s = Σ p(label) · polarity(label)`, with
`polarity` from the catalog (−1 … +1). This one number works for 2-class,
3-class and 1–5-star models alike. A positive word weight means the word pushed
toward positive sentiment, whatever label won. The UI colours it blue; negative
is red.

## How

1. Tokenise with offsets and `return_special_tokens_mask=True`. Only tokens the
   tokenizer *added* (`[CLS]`, `[SEP]`, `<s>`, `</s>`) count as special. `[UNK]`
   (for example an emoji for uncased BERT) is text and gets attributed. Don't
   use `tokenizer.get_special_tokens_mask(..., already_has_special_tokens=True)`:
   it marks `[UNK]` as special.
2. Baseline: every ordinary token replaced by `[PAD]`, special tokens kept.
3. Interpolate the input embeddings from the baseline along a straight line,
   `steps` midpoints, in chunks of 8. Take the gradient of `s` with respect to
   the embeddings (`torch.enable_grad()`, parameters frozen), and average.
4. The token score is `(input − baseline) · mean gradient`, summed over the
   hidden dimension. Special tokens get 0.
5. Map tokens to words (`word_weights`). Each token goes to the whitespace
   segment holding its first non-space character. Whitespace-only tokens
   (RoBERTa's extra `Ġ`, tabs, newlines) go to the next word, or the previous
   one at the end. Nothing is dropped: the sum of word weights equals the sum of
   token scores (tested).
6. Normalise by the strongest word to [−1, 1]. The output covers the original
   text segment by segment, whitespace included (weight 0). Model preprocessing
   (`@user`) replaces whole words, so segments line up with the user's text.

**Check:** integrated gradients' completeness axiom, that the attribution sum
equals f(input) − f(baseline), is asserted for all three architectures in
`test_integrated_gradients_is_complete` (64 steps, within 5%). If you change
this code, keep that test green.

## Cost and settings

- Cost: `steps` forward and backward passes over the text (in chunks of 8), on
  top of the prediction. With 16 steps on CPU, a short review adds tens of ms on
  DistilBERT; a 512-token text on BERT-base can take seconds.
- `EXPLAIN_STEPS=16` is the default: good enough for word-level colour. Use
  32–64 for publication-quality attributions, or `0` to turn explanations off
  (the UI then hides the section).
- Batch predictions never explain.
- `inputs_embeds` is required. BERT, DistilBERT, RoBERTa, XLM-R, ELECTRA, ALBERT
  and DeBERTa support it; most encoders do.

## Reading it honestly (UI copy)

Attributions show what moved *this model's* output. They don't show what a
human would call the sentiment words, and small models attribute function words
too. The UI labels the section "Word influence · Integrated gradients", and keeps
the weight in each word's tooltip.
