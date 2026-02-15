# Frontend - Advanced RAG System

A modern, responsive single-page application built with vanilla HTML, CSS, and JavaScript.

## 🎨 Features

### **Modern Design**
- Dark theme with gradient accents
- Glassmorphism effects
- Smooth animations and transitions
- Responsive layout (mobile-friendly)

### **File Upload**
- Drag & drop support
- Progress indicator
- File type validation (PDF, TXT, MD)
- Success/error feedback

### **Chat Interface**
- Real-time messaging
- Typing indicators
- Message formatting
- Citation display
- Conversation memory

### **Status Monitoring**
- Server connection status
- Real-time health checks
- Visual indicators

## 🚀 Quick Start

### **1. Start Backend**
```bash
# From project root
uv run python backend/api/main.py
```

### **2. Open Browser**
Navigate to: `http://localhost:8000`

The frontend is automatically served by FastAPI!

## 📁 File Structure

```
frontend/
├── index.html    # Main HTML structure
├── styles.css    # Styling and animations
└── app.js        # Application logic
```

## 🎯 Usage

### **Upload Documents**
1. Click or drag & drop files into the upload area
2. Supported formats: PDF, TXT, MD
3. Wait for processing confirmation

### **Ask Questions**
1. Type your question in the chat input
2. Press Enter or click send button
3. View answer with citations
4. Ask follow-up questions (conversation memory enabled)

## 🎨 Design System

### **Colors**
- Primary: `#6366f1` (Indigo)
- Secondary: `#8b5cf6` (Purple)
- Success: `#10b981` (Green)
- Error: `#ef4444` (Red)

### **Typography**
- Font: System fonts (San Francisco, Segoe UI, Roboto)
- Sizes: Responsive (0.75rem - 1.5rem)

### **Spacing**
- XS: 0.5rem
- SM: 1rem
- MD: 1.5rem
- LG: 2rem
- XL: 3rem

## 🔧 Customization

### **Change API URL**
Edit `app.js`:
```javascript
const API_BASE_URL = 'http://your-api-url:port';
```

### **Modify Theme**
Edit CSS variables in `styles.css`:
```css
:root {
    --primary: #6366f1;
    --bg-primary: #0f172a;
    /* ... */
}
```

## 📱 Responsive Design

The frontend is fully responsive and works on:
- Desktop (1200px+)
- Tablet (768px - 1199px)
- Mobile (< 768px)

## ✨ Features Showcase

### **Animations**
- Slide-in messages
- Typing indicators
- Progress bars
- Hover effects
- Button interactions

### **User Experience**
- Auto-scroll to latest message
- Keyboard shortcuts (Enter to send)
- Loading states
- Error handling
- Auto-hide notifications

## 🚀 Production Deployment

### **Build for Production**
No build step required! Pure HTML/CSS/JS.

### **Serve with FastAPI**
Already configured in `backend/api/main.py`:
```python
app.mount("/static", StaticFiles(directory="frontend"))
app.get("/")(serve_frontend)
```

### **Deploy to CDN**
Upload `frontend/` folder to any static hosting:
- Netlify
- Vercel
- GitHub Pages
- AWS S3 + CloudFront

Update `API_BASE_URL` to point to your backend.

## 🎯 Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers

## 📝 Code Structure

### **HTML (`index.html`)**
- Semantic HTML5
- Accessibility features
- SEO meta tags
- SVG icons

### **CSS (`styles.css`)**
- CSS Variables
- Flexbox & Grid
- Animations
- Media queries
- Custom scrollbars

### **JavaScript (`app.js`)**
- ES6+ syntax
- Async/await
- Fetch API
- DOM manipulation
- Error handling

## 🎨 UI Components

### **Cards**
Glassmorphism effect with backdrop blur

### **Buttons**
Gradient backgrounds with hover effects

### **Inputs**
Focus states with border animations

### **Messages**
Bubble design with different styles for user/assistant

### **Citations**
Collapsible source references

## 🔒 Security

- XSS protection (content sanitization)
- CORS enabled
- File type validation
- Error boundary

## 📊 Performance

- Minimal dependencies (vanilla JS)
- Lazy loading
- Optimized animations
- Efficient DOM updates

## 🎉 No Framework Required!

Built with pure HTML, CSS, and JavaScript. No build tools, no dependencies, no complexity!
