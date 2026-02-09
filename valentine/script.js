(function () {
    const questionScreen = document.getElementById('question-screen');
    const yesScreen = document.getElementById('yes-screen');
    const btnYes = document.getElementById('btn-yes');
    const btnNo = document.getElementById('btn-no');
    const buttonsContainer = document.querySelector('.buttons');

    // Visible area (phone: avoids keyboard/address bar; desktop: full window)
    function getSafeBounds() {
        const v = window.visualViewport;
        const w = (v && v.width)  ? v.width  : window.innerWidth;
        const h = (v && v.height) ? v.height : window.innerHeight;
        const ox = (v && v.offsetLeft) ? v.offsetLeft : 0;
        const oy = (v && v.offsetTop)  ? v.offsetTop  : 0;
        return { w, h, ox, oy };
    }

    // Move "No" to a random spot but always inside the visible screen
    function moveNoButton() {
        const { w, h, ox, oy } = getSafeBounds();
        const btnRect = btnNo.getBoundingClientRect();
        const btnW = btnRect.width;
        const btnH = btnRect.height;

        const margin = 12;
        const minX = ox + margin;
        const minY = oy + margin;
        const maxX = ox + Math.max(0, w - btnW - margin);
        const maxY = oy + Math.max(0, h - btnH - margin);

        let newX = minX + Math.random() * Math.max(0, maxX - minX);
        let newY = minY + Math.random() * Math.max(0, maxY - minY);
        newX = Math.max(minX, Math.min(maxX, newX));
        newY = Math.max(minY, Math.min(maxY, newY));

        // Keep away from "Yes" button
        const yesRect = btnYes.getBoundingClientRect();
        const safeDist = 70;
        for (let i = 0; i < 20; i++) {
            const dx = newX - yesRect.left;
            const dy = newY - yesRect.top;
            if (Math.abs(dx) < safeDist && Math.abs(dy) < safeDist) {
                newX = minX + Math.random() * Math.max(0, maxX - minX);
                newY = minY + Math.random() * Math.max(0, maxY - minY);
                newX = Math.max(minX, Math.min(maxX, newX));
                newY = Math.max(minY, Math.min(maxY, newY));
            } else break;
        }

        btnNo.style.position = 'fixed';
        btnNo.style.left = newX + 'px';
        btnNo.style.top = newY + 'px';
        btnNo.style.transform = 'scale(1.02)';
        btnNo.style.transition = 'left 0.3s ease-out, top 0.3s ease-out';
    }

    btnNo.addEventListener('mouseenter', moveNoButton);
    btnNo.addEventListener('click', function (e) {
        e.preventDefault();
        moveNoButton();
    });

    // Confetti for "Yes"
    function createConfetti() {
        const container = document.querySelector('.confetti');
        const colors = ['#e8a0a0', '#c77b7b', '#ffb6c1', '#d4a574', '#fff0f3'];
        const shapes = ['♥', '💕', '💖', '•'];

        for (let i = 0; i < 60; i++) {
            const piece = document.createElement('div');
            piece.className = 'confetti-piece';
            piece.textContent = shapes[Math.floor(Math.random() * shapes.length)];
            piece.style.cssText = `
                position: absolute;
                left: ${Math.random() * 100}vw;
                top: -20px;
                color: ${colors[Math.floor(Math.random() * colors.length)]};
                font-size: ${14 + Math.random() * 20}px;
                opacity: 0.9;
                animation: fall ${3 + Math.random() * 4}s linear forwards;
                animation-delay: ${Math.random() * 0.5}s;
                pointer-events: none;
            `;
            container.appendChild(piece);

            setTimeout(() => piece.remove(), 8000);
        }
    }

    // Add confetti fall animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fall {
            to {
                transform: translateY(100vh) rotate(720deg);
            }
        }
    `;
    document.head.appendChild(style);

    // "Yes" clicked: show celebration
    btnYes.addEventListener('click', function () {
        questionScreen.classList.add('hidden');
        questionScreen.style.display = 'none';
        yesScreen.classList.remove('hidden');
        yesScreen.style.display = 'flex';
        createConfetti();
    });
})();
