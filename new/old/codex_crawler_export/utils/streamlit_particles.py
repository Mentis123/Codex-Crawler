import streamlit as st

def add_particles():
    """
    Add particle effect to Streamlit app using tsParticles library
    This approach is more compatible with Streamlit's iframe sandbox
    """
    # CSS for styling
    st.markdown("""
    <style>
    #tsparticles {
        position: fixed;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
        z-index: -1;
    }
    
    .stApp {
        background: transparent !important;
    }
    
    .main .block-container {
        background: rgba(14, 17, 23, 0.7) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Load tsParticles and its dependencies
    st.markdown("""
    <div id="tsparticles"></div>
    <script src="https://cdn.jsdelivr.net/npm/tsparticles@2.12.0/tsparticles.bundle.min.js"></script>
    <script>
        // Initialize tsParticles
        (function() {
            const init = async function() {
                console.log("Initializing particles");
                try {
                    await tsParticles.load("tsparticles", {
                        fullScreen: false,
                        background: {
                            color: {
                                value: "#0e1117"
                            }
                        },
                        fpsLimit: 60,
                        interactivity: {
                            events: {
                                onClick: {
                                    enable: true,
                                    mode: "push"
                                },
                                onHover: {
                                    enable: true,
                                    mode: "repulse"
                                },
                                resize: true
                            },
                            modes: {
                                push: {
                                    quantity: 4
                                },
                                repulse: {
                                    distance: 100,
                                    duration: 0.4
                                }
                            }
                        },
                        particles: {
                            color: {
                                value: "#3fcc66"
                            },
                            links: {
                                color: "#00d9ff",
                                distance: 150,
                                enable: true,
                                opacity: 0.5,
                                width: 1
                            },
                            move: {
                                direction: "none",
                                enable: true,
                                outModes: {
                                    default: "bounce"
                                },
                                random: false,
                                speed: 2,
                                straight: false
                            },
                            number: {
                                density: {
                                    enable: true,
                                    area: 800
                                },
                                value: 80
                            },
                            opacity: {
                                value: 0.5
                            },
                            shape: {
                                type: "circle"
                            },
                            size: {
                                value: { min: 1, max: 5 }
                            }
                        },
                        detectRetina: true
                    });
                    console.log("Particles initialized successfully");
                } catch (error) {
                    console.error("Failed to initialize particles:", error);
                }
            };
            
            // Load when document is ready
            if (document.readyState === "complete" || document.readyState === "interactive") {
                setTimeout(init, 500);
            } else {
                document.addEventListener("DOMContentLoaded", function() {
                    setTimeout(init, 500);
                });
            }
            
            // Also try on window load as fallback
            window.addEventListener("load", function() {
                setTimeout(init, 500);
            });
        })();
    </script>
    """, unsafe_allow_html=True)