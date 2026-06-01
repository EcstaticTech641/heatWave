import streamlit as st

def main():
    st.title("heatWave: Psych-to-Heat Converter")
    st.write("Upload a USA Swimming psych sheet PDF to generate a heat sheet.")
    
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    if uploaded_file is not None:
        st.success("File uploaded successfully! (Parsing logic to be implemented)")
        # TODO: integrate extractor and seeder

if __name__ == "__main__":
    main()
