import streamlit as st
import httpx
import os
import json
from dotenv import load_dotenv

# Load credentials securely from your .env file
load_dotenv()

CLOCKED_API_KEY = os.getenv("CLOCKED_API_KEY")
CLOCKED_API_URL = os.getenv("CLOCKED_API_URL", "https://clocked.ai")

st.set_page_config(page_title="AuditTrail AI Dashboard", page_icon="🛡️", layout="wide")

st.title("🛡️ AuditTrail AI: Document Compliance Portal")
st.markdown("---")

# Layout Input Sections
col1, col2 = st.columns(2)

with col1:
    document_text = st.text_area(
        "Target Document Payload (Lease Deed / Abstract)", 
        placeholder="Paste unstructured document text context here...",
        height=250
    )

with col2:
    compliance_rules = st.text_area(
        "Regional Regulatory Reference Master (Zoning Rules)", 
        placeholder="Paste targeted regional regulations or municipal code constraints here...",
        height=250
    )

if st.button("Execute Compliance Pipeline", type="primary", use_container_width=True):
    if not document_text or not compliance_rules:
        st.error("Please ensure both input fields are fully populated.")
    elif not CLOCKED_API_KEY:
        st.error("Missing CLOCKED_API_KEY inside your .env configuration file.")
    else:
        # Create execution animation wrappers matching hackathon requirements
        progress_bar = st.progress(0, text="Initializing Pipeline Node Secure Handshake...")
        
        try:
            headers = {
                "Authorization": f"Bearer {CLOCKED_API_KEY}",
                "Content-Type": "application/json"
            }
            
            with httpx.Client(base_url=CLOCKED_API_URL, headers=headers, timeout=60.0) as client:
                
                # --- STEP 1: PROTECT ---
                progress_bar.progress(33, text="[STEP 1] Masking Data: Scrubbing private PII profiles...")
                mask_payload = {
                    "text": document_text,
                    "mask_types": ["NAME", "SSN", "FINANCIAL_RECORD", "PHONE_NUMBER"],
                    "replacement": "[MASKED]"
                }
                mask_res = client.post("/protect", json=mask_payload)
                if mask_res.status_code != 200:
                    raise Exception(f"Protect Node rejected payload (Status {mask_res.status_code})")
                
                masked_text = mask_res.json().get("masked_text", document_text)
                detected_entities = mask_res.json().get("detected_entities", [])
                
                # --- STEP 2: VERIFY ---
                progress_bar.progress(66, text="[STEP 2] Verifying: Evaluating text grounding structural bounds...")
                grounding_payload = {
                    "claim_text": masked_text,
                    "source_context": compliance_rules,
                    "strict_mode": True
                }
                verify_res = client.post("/verify", json=grounding_payload)
                if verify_res.status_code != 200:
                    raise Exception(f"Verify Node rejected payload (Status {verify_res.status_code})")
                    
                verify_data = verify_res.json()
                
                # --- STEP 3: DECIDE ---
                progress_bar.progress(90, text="[STEP 3] Computing Risk: Extracting structured classification fields...")
                decision_payload = {
                    "context": masked_text,
                    "grounding_data": verify_data,
                    "schema_format": {
                        "compliance_risk_detected": "boolean",
                        "classification": "string",
                        "action_required": "boolean"
                    }
                }
                decide_res = client.post("/decide", json=decision_payload)
                if decide_res.status_code != 200:
                    raise Exception(f"Decide Node rejected payload (Status {decide_res.status_code})")
                    
                decision_data = decide_res.json()
                
                # Complete the animation bar
                progress_bar.progress(100, text="Pipeline Execution Complete!")
                st.success("Analysis round-trip fulfilled successfully.")
                st.markdown("---")
                
                # --- RENDER DASHBOARD VISUALS ---
                res_col1, res_col2 = st.columns()
                
                structured_output = decision_data.get("structured_output", {})
                citations = verify_data.get("source_positions", [])

                with res_col1:
                    st.subheader("📊 Risk Summary Matrix")
                    st.metric("Risk Classification", str(structured_output.get("classification", "HIGH_RISK")))
                    st.metric("Masked Entities Flagged", f"{len(detected_entities)} items")
                    st.write(f"**Action Required:** {str(structured_output.get('action_required', True))}")
                    
                    # --- NEW ADDED FEATURE: EXPORT INTERACTIVE REPORT ---
                    st.markdown("### 📥 Compliance Artifacts")
                    markdown_report = f"""# AuditTrail AI Compliance Report
## Summary Metrics
- **Risk Classification:** {structured_output.get('classification', 'HIGH_RISK')}
- **Action Required:** {structured_output.get('action_required', True)}
- **Masked PII Counterparts:** {len(detected_entities)} items

## Absolute Mapped Index Citations
{json.dumps(citations, indent=2) if citations else "No structural compliance anomalies mapped."}

## Masked Document Payload
```markdown
{masked_text}
```
"""
                    st.download_button(
                        label="Download Full Audit Report (.md)",
                        data=markdown_report,
                        file_name="audittrail_compliance_report.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                
                with res_col2:
                    st.subheader("📑 Indexed Absolute Match Table")
                    if citations:
                        st.table(citations)
                    else:
                        st.info("No compliance contract anomalies mapped to indices.")
                        
                    st.subheader("🔒 Masked Storage Output Preview")
                    st.code(masked_text, language="markdown")
                    
        except Exception as e:
            progress_bar.empty()
            st.error(f"Pipeline execution failure: {str(e)}")
