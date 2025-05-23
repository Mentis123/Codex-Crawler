
import streamlit as st

def add_vanta_effect():
    """Add a Vanta.js bioluminescent background effect to the Streamlit app."""
    st.markdown("""
        <div id="vanta-container"></div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.dots.min.js"></script>

        <style>
        #vanta-container {
            position: fixed !important;
            z-index: 0;
            left: 0;
            top: 0;
            width: 100vw;
            height: 100vh;
            pointer-events: none;
        }

        .stApp {
            background: transparent !important;
        }

        .main .block-container {
            background: rgba(14, 17, 23, 0.45) !important;
            position: relative;
            z-index: 1;
        }

        .stMarkdown, .stButton, .stDownloadButton {
            position: relative;
            z-index: 1;
            background: rgba(14, 17, 23, 0.2);
            border-radius: 4px;
            padding: 4px;
        }
        </style>

        <script>
        document.addEventListener('DOMContentLoaded', function() {
            VANTA.DOTS({
                el: "#vanta-container",
                mouseControls: true,
                touchControls: true,
                gyroControls: false,
                minHeight: 200.00,
                minWidth: 200.00,
                scale: 1.00,
                scaleMobile: 1.00,
                color: 0x228B22,
                color2: 0x00CED1,
                backgroundColor: 0x0E1517,
                size: 1.20,
                speed: 0.80,
                spacing: 15.00
            });
        });
        </script>
    """, unsafe_allow_html=True)
