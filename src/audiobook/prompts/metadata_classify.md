You are deciding whether a metadata block from a document should be
included in an audiobook narration.

Classify the block as SKIP or MENTION.

SKIP when the block is:
- Copyright notices, license text, DOIs, ISBNs
- ACM/IEEE reference format blocks
- Author email addresses or ORCID links
- Page numbers, conference venue logistics
- Raw URLs or hyperlinks

MENTION when the block is:
- Author names worth crediting
- The paper or book title
- Important dates or version info

Respond with exactly one line:
  SKIP
or
  MENTION: [one-sentence spoken version]

Examples:
  Input: "This work is licensed under CC BY 4.0..."
  Output: SKIP

  Input: "John Smith, Jane Doe - Stanford University"
  Output: MENTION: This work was authored by John Smith and Jane Doe from Stanford University.