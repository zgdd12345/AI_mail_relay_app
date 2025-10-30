#!/usr/bin/env python3
"""Test single paper processing with research field extraction."""

from dotenv import load_dotenv
load_dotenv()

from src.ai_mail_relay.arxiv_parser import ArxivPaper
from src.ai_mail_relay.llm_client import LLMClient
from src.ai_mail_relay.config import Settings

# Load settings
settings = Settings()

# Create a sample paper
test_paper = ArxivPaper(
    title="Attention Is All You Need",
    authors="Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin",
    categories=["cs.CL", "cs.LG"],
    abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
    links=["https://arxiv.org/abs/1706.03762"],
    arxiv_id="1706.03762",
)

print("=" * 80)
print("Testing Single Paper Processing")
print("=" * 80)
print(f"\nPaper Title: {test_paper.title}")
print(f"Authors: {test_paper.authors}")
print(f"Categories: {', '.join(test_paper.categories)}")
print(f"arXiv ID: {test_paper.arxiv_id}")
print("\n" + "=" * 80)
print("Calling LLM to generate summary...")
print("=" * 80 + "\n")

# Initialize LLM client
llm_client = LLMClient(settings.llm)

# Process single paper
try:
    summary = llm_client.summarize_single_paper(test_paper)

    print("Raw LLM Response:")
    print("-" * 80)
    print(summary)
    print("-" * 80)

    # Extract metadata
    llm_client._extract_paper_metadata(summary, test_paper)

    print("\nExtracted Metadata:")
    print("-" * 80)
    print(f"Research Field: {test_paper.research_field or '(not extracted)'}")
    print(f"Work Summary: {test_paper.summary or '(not extracted)'}")
    print("-" * 80)

    if test_paper.research_field and test_paper.summary:
        print("\n✓ SUCCESS: Both research field and work summary extracted!")
    else:
        print("\n✗ WARNING: Some fields not extracted")
        if not test_paper.research_field:
            print("  - Missing: research_field")
        if not test_paper.summary:
            print("  - Missing: summary")

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
