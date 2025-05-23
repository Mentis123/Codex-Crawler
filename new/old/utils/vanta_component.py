
import streamlit as st

def inject_vanta_background():
    """Inject a Vanta.js dots background effect."""
    st.markdown("""
        <div id="vanta-bg"></div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.net.min.js"></script>
        <style>
            #vanta-bg {
                position: fixed !important;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: -1;
            }
            .stApp {
                background: transparent !important;
            }
            .main .block-container {
                background: rgba(14, 17, 23, 0.8) !important;
                backdrop-filter: blur(5px);
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Add a separate script element that's injected after the page is loaded
    st.markdown("""
        <script type="text/javascript">
            // Console logs to debug
            console.log('Vanta script started');
            
            // Function to initialize Vanta
            function initVanta() {
                try {
                    console.log('Initializing Vanta effect');
                    console.log('VANTA available:', typeof VANTA !== 'undefined');
                    console.log('THREE available:', typeof THREE !== 'undefined');
                    
                    // Check if all dependencies are loaded
                    if (typeof VANTA !== 'undefined' && typeof THREE !== 'undefined') {
                        console.log('Creating Vanta effect');
                        // Clean up any previous effect
                        if (window.vantaEffect) {
                            window.vantaEffect.destroy();
                        }
                        
                        // Create new effect
                        window.vantaEffect = VANTA.NET({
                            el: document.getElementById('vanta-bg'),
                            mouseControls: true,
                            touchControls: true,
                            gyroControls: false,
                            minHeight: 200.00,
                            minWidth: 200.00,
                            scale: 1.00,
                            scaleMobile: 1.00,
                            color: 0x3fcc66,
                            backgroundColor: 0x0e1117,
                            points: 15.00,
                            maxDistance: 25.00,
                            spacing: 17.00,
                            showDots: true
                        });
                        console.log('Vanta effect created');
                    } else {
                        console.log('VANTA or THREE not available yet, retrying in 500ms');
                        setTimeout(initVanta, 500);
                    }
                } catch (e) {
                    console.error('Error initializing Vanta effect:', e);
                }
            }
            
            // Retry logic to ensure effect is loaded
            let retryCount = 0;
            const maxRetries = 5;
            
            function attemptInit() {
                if (retryCount < maxRetries) {
                    retryCount++;
                    console.log(`Attempt ${retryCount} to initialize Vanta`);
                    initVanta();
                    setTimeout(attemptInit, 1000);
                }
            }
            
            // Initial attempt
            if (document.readyState === 'complete') {
                console.log('Document already complete, initializing now');
                setTimeout(attemptInit, 100);
            } else {
                console.log('Waiting for document to be ready');
                document.addEventListener('DOMContentLoaded', function() {
                    console.log('DOMContentLoaded fired');
                    setTimeout(attemptInit, 100);
                });
                
                // Backup in case DOMContentLoaded doesn't fire properly in iframes
                window.addEventListener('load', function() {
                    console.log('Window load event fired');
                    setTimeout(attemptInit, 100);
                });
            }
        </script>
    """, unsafe_allow_html=True)
