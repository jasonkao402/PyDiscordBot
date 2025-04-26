const ws = new WebSocket(`ws://${location.host}/ws/dashboard`);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);  // 變成 JSON格式
    const sessionId = data.session_id;
    const reply = data.reply;

    // 自動為每個不同 sessionId 建一個子區域
    let sessionDiv = document.getElementById(sessionId);
    if (!sessionDiv) {
        sessionDiv = document.createElement("div");
        sessionDiv.id = sessionId;
        sessionDiv.className = "session";
        const title = document.createElement("h2");
        title.textContent = `Session: ${sessionId}`;
        sessionDiv.appendChild(title);
        document.getElementById("sessions").appendChild(sessionDiv);
    }

    const replyBlock = document.createElement("div");
    replyBlock.className = "reply-block";

    const replyPara = document.createElement("p");
    replyPara.textContent = `Reply: ${reply}`;
    replyBlock.appendChild(replyPara);

    const timerSpan = document.createElement("span");
    timerSpan.className = "timer";
    timerSpan.textContent = "10";
    replyBlock.appendChild(timerSpan);

    const progressContainer = document.createElement("div");
    progressContainer.className = "progress-bar-container";
    const progressBar = document.createElement("div");
    progressBar.className = "progress-bar";
    progressContainer.appendChild(progressBar);
    replyBlock.appendChild(progressContainer);

    // 控制按鈕
    const controlsDiv = document.createElement("div");
    controlsDiv.className = "controls";
    const sendBtn = document.createElement("button");
    sendBtn.textContent = "Send";
    const cancelBtn = document.createElement("button");
    cancelBtn.textContent = "Cancel";

    controlsDiv.appendChild(sendBtn);
    controlsDiv.appendChild(cancelBtn);
    replyBlock.appendChild(controlsDiv);

    sessionDiv.appendChild(replyBlock);

    let countdown = 10;
    const interval = setInterval(() => {
        countdown--;
        timerSpan.textContent = countdown;
        progressBar.style.width = `${((10 - countdown) / 10) * 100}%`;
        if (countdown <= 0) {
            clearInterval(interval);
            sendReply();
        }
    }, 1000);

    function sendReply() {
        ws.send(JSON.stringify({ action: "SEND", session_id: sessionId, reply: reply }));
        replyBlock.remove();
    }

    function cancelReply() {
        ws.send(JSON.stringify({ action: "CANCEL", session_id: sessionId, reply: reply }));
        replyBlock.remove();
    }

    sendBtn.onclick = () => {
        clearInterval(interval);
        sendReply();
    };

    cancelBtn.onclick = () => {
        clearInterval(interval);
        cancelReply();
    };
};
