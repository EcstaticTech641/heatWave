# HeatWave Streamlit UI - User Guide

## Quick Start

### For Coaches (Easy Way)

1. **Start the app:**
   ```bash
   python run_streamlit.py
   ```
   The app opens in your browser at `http://localhost:8501`

2. **Upload your psych sheet:**
   - Click the **Upload** tab
   - Drag and drop your USA Swimming psych sheet PDF
   - Click **Parse PDF** button

3. **Review the data:**
   - Go to **Preview** tab
   - Check that events and entries are correct
   - Filter by event type if needed

4. **Customize settings:**
   - Go to **Settings** tab
   - Enter meet title (e.g., "Oklahoma 10-Under Championships")
   - Set meet date (format: MM/DD/YYYY)
   - Adjust pool lanes (usually 8)

5. **Generate heat sheets:**
   - Go to **Generate** tab
   - Click **Generate Heat Sheets** button
   - Wait for processing (takes a few seconds)
   - Download the PDF files

6. **Use at the meet:**
   - Print the full meet PDF (one copy for each official)
   - Or print individual event sheets as needed
   - Coaches use these to time the swimmers

---

## Features Overview

### 📤 Upload Tab
- Drag-and-drop PDF upload
- File size display
- Quick statistics after parsing
  - Total events
  - Relay vs individual events
  - Total entries

### 👀 Preview Tab
- View all parsed events
- Filter by event type (All/Individual/Relay)
- Search by event name
- See sample entries for each event
- Verify data accuracy before generating

### ⚙️ Settings Tab
- **Meet Title:** Name of the meet (displayed on heat sheets)
- **Meet Date:** Date to print on heat sheets
- **Number of Lanes:** Pool configuration (4-10 lanes, typically 8)
- Real-time preview of settings

### 📊 Generate Tab
- Review configuration before generating
- Progress indicators during seeding
- Heat statistics:
  - Total heats created
  - Average entries per heat
  - Largest/smallest event
  - Heat distribution details
- Download options:
  - Full meet PDF (all events in one document)
  - Individual event PDFs (one sheet per event)

---

## Understanding Heat Seeding

The app uses **official USA Swimming seeding rules**:

### How Heats Are Assigned
1. **Swimmers sorted by time** - Slowest to fastest
2. **Heats filled sequentially** - All fastest swimmers go to Heat 1, next fastest to Heat 2, etc.
3. **Lane placement (center-out)** - Within each heat:
   - Lane 4: Fastest (center-left)
   - Lane 5: Second fastest (center-right)
   - Lane 3: Third fastest
   - Lane 6: Fourth fastest
   - And so on outward

### Lane Pattern for 8-Lane Pool
```
Placement Order (by speed):
Lane 4 → Lane 5 → Lane 3 → Lane 6 → Lane 2 → Lane 7 → Lane 1 → Lane 8
```

This ensures:
- Fastest swimmers race in center lanes (most consistent)
- Heats are evenly distributed
- Fair competition according to USA Swimming standards

---

## PDF Output

### Full Meet PDF
- **What:** All events in one PDF document
- **Pages:** Usually 1 cover + 1-2 pages per event
- **Use:** Hand to meet officials
- **File name:** `HeatSheet_[Meet_Name].pdf`

### Individual Event PDFs
- **What:** One PDF per event
- **Use:** Give to event organizers/timers
- **File names:** `Event_01_Heatsheet.pdf`, `Event_02_Heatsheet.pdf`, etc.

### PDF Content
Each heat sheet shows:
- Meet name and date
- Event number, gender, distance, and stroke
- Heat-by-heat assignments:
  - Lane number (1-8)
  - Swimmer name
  - Age (for individuals)
  - Team code
  - Seed time
  - Original placement number

---

## Tips & Troubleshooting

### ✅ Best Practices
1. **Always preview first** - Check that events parsed correctly
2. **Verify meet info** - Make sure date and title are correct
3. **Confirm pool lanes** - Use 8 unless your pool is different
4. **Print a test page** - Check formatting before final print

### ❌ Common Issues

**"Error processing PDF"**
- Make sure you have a valid USA Swimming psych sheet
- File should be in standard PDF format
- Try again with a different psych sheet

**"No events found"**
- PDF might be in an unexpected format
- Make sure it's a USA Swimming psych sheet (not a different format)

**"Missing swimmers in preview"**
- This is fine! The app extracts what's in the PDF
- If a swimmer is missing from the psych sheet, it won't appear in seeding

**"Event names look wrong"**
- The app tries to parse event names from the PDF
- Check the Preview tab to see exactly what was extracted
- You can still generate heats - the seeding works by entry count

### 🔄 Redo Everything
1. Refresh the page (Ctrl+R or Cmd+R)
2. Start over with a new PDF
3. All session data is cleared

---

## Technical Details (For Administrators)

### System Requirements
- Python 3.11 or higher
- ~200 MB disk space
- Modern web browser

### Installation (First Time)
```bash
cd heatWave
pip install -r requirements.txt
```

### Running the App
```bash
python run_streamlit.py
```

### Performance
- Typical psych sheet (700 entries): < 5 seconds
- PDF generation: < 3 seconds
- Works offline (no internet needed)

### File Size
- Input PDF: ~80 KB
- Output PDFs: ~80-90 KB total
- No files stored on disk (cleaned up automatically)

---

## FAQ

**Q: Can I edit the seeding after generation?**
A: Not yet. You can generate new heat sheets by re-uploading the PDF with different settings.

**Q: What if a swimmer needs to be scratched?**
A: Re-generate with an updated psych sheet that excludes the scratched swimmer.

**Q: Can I use this for other meet types?**
A: Currently designed for USA Swimming. International formats may not parse correctly.

**Q: Is my data secure?**
A: Yes. The app runs entirely on your computer. No data is uploaded or stored anywhere.

**Q: What if I find a bug?**
A: Report it to the heatWave development team with:
- The problematic PDF (if possible)
- What went wrong
- Your Python and Streamlit versions

---

## Support

For questions or problems:
1. Check the **Preview tab** to verify data extraction
2. Re-read the **Tips & Troubleshooting** section above
3. Contact the heatWave support team

**Contact:** heatwave@example.com

---

**Version:** 1.0  
**Last Updated:** April 2026  
**Made for USA Swimming Coaches**
