function loadCommitList() {
  // 커밋 카드 목록 갱신 후
  const cards = document.querySelectorAll(".commit-card");
  cards.forEach(card => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".commit-card").forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
    });
  });
}


async function submitRevision() {
  const revisionInput = document.getElementById("revision-input").value.trim();
  const selectedCard = document.querySelector(".commit-card.selected");

  if (!selectedCard) {
    alert("먼저 히스토리에서 수정할 항목을 선택해주세요.");
    return;
  }

  if (!revisionInput) {
    alert("수정 요청 내용을 입력해주세요.");
    return;
  }

  // 커밋 ID는 card의 id 속성에서 추출 (ex: commit-abcdef → abcdef)
  const selectedCommitId = selectedCard.id.replace("commit-", "");

  try {
    const res = await fetch("/revise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commit_id: selectedCommitId,
        prompt: revisionInput,
      }),
    });

    const result = await res.json();

    if (res.ok && result.status === "success") {
      alert("✅ 수정 요청 완료! 미리보기에서 확인하세요.");
      document.getElementById("revision-input").value = "";

      // 👉 미리보기 프레임 반영
      document.getElementById("preview-frame").src = result.preview_url;
      document.getElementById("preview-frame").dataset.commitId = result.commit_id;

      loadCommitList();  // 새로운 커밋 목록 반영
    } else {
      alert("❌ 수정 실패: " + (result.message || result.error || "서버 오류"));
    }

  } catch (error) {
    console.error("[submitRevision] error:", error);
    alert("서버 오류 발생: " + error.message);
  }
}


// 토스트 메시지
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 2500);
}

// 프롬프트 생성 요청
document.getElementById('submit-btn').addEventListener('click', async () => {
  const prompt = document.getElementById('prompt-input').value.trim();
  if (!prompt) return showToast('⚠️ 프롬프트를 입력해주세요.');

  document.getElementById('loading-indicator').style.display = 'inline';
  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt + "\n\n반드시 <html>…</html> 전체 구조의 HTML을 출력해 주세요." })
    });
	  
    const data = await res.json();
    if (data.commit_id) {
      document.getElementById('preview-frame').src = `/preview/${data.commit_id}`;
      document.getElementById('preview-frame').dataset.commitId = data.commit_id;
      showToast('✅ 생성 완료!');
      fetchCommitHistory();
    } else {
      showToast('❌ 생성 실패');
    }
  } catch (e) {
    showToast('❌ 오류: ' + e.message);
  } finally {
    document.getElementById('loading-indicator').style.display = 'none';
  }
});

// 승인 후 배포
document.getElementById('approve-btn').addEventListener('click', async () => {
  const commitId = document.getElementById('preview-frame').dataset.commitId;
  if (!commitId) return showToast('❗ 미리보기 커밋이 없습니다.');
  
  // /admin/approve/:commit_id 엔드포인트 호출 (body 불필요)
  const res = await fetch(`/admin/approve/${commitId}`, {
    method: 'POST'
  });
	
  showToast(res.ok ? '🚀 배포 완료!' : '❌ 배포 실패');
  fetchCommitHistory();
});

// 사이드바 토글
document.getElementById('toggle-sidebar-btn').addEventListener('click', () => {
  const sb = document.querySelector('.sidebar');
  if (sb.style.display === 'none') {
    sb.style.display = 'block'; showToast('📂 히스토리 열기');
  } else {
    sb.style.display = 'none';  showToast('📁 히스토리 닫기');
  }
});

// 커밋 히스토리 불러오기
async function fetchCommitHistory() {
  const res = await fetch('/admin/logs');
  const data = await res.json();
  const list = document.getElementById('commit-list');
  list.innerHTML = '';
  (data.logs || []).reverse().forEach((c, i) => {
    const div = document.createElement('div');
    div.className = 'commit-card' + (i === 0 ? ' latest-commit' : '');
    div.id = `commit-${c.commit_id}`;  // <- 이 ID가 있어야 수정 시 추출 가능
    div.innerHTML = `
      <strong>${c.commit_id}</strong><br>
      ${c.prompt}<br>
      ${c.timestamp}<br>
      <button class="rollback-btn" data-commit-id="${c.commit_id}">🔙 롤백</button>
    `;
    list.appendChild(div);
  });
  loadCommitList();
}

// 롤백 모달
document.addEventListener('click', e => {
  if (e.target.classList.contains('rollback-btn')) {
    const id = e.target.dataset.id;
    const m = document.getElementById('rollback-modal');
    m.style.display = 'flex'; m.dataset.commitId = id;
  }
});
document.getElementById('cancel-rollback').addEventListener('click', () => {
  document.getElementById('rollback-modal').style.display = 'none';
});
document.getElementById('confirm-rollback').addEventListener('click', async () => {
  const m = document.getElementById('rollback-modal');
  const id = m.dataset.commitId; m.style.display = 'none';
  const res = await fetch('/admin/rollback', {
    method: 'POST',   
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer admin-secret-token-here'
    },
    body: JSON.stringify({ commit_id: id })
  });
  showToast(res.ok ? '🔙 롤백 성공' : '❌ 롤백 실패');
  fetchCommitHistory();
});

// 초기 로드
fetchCommitHistory().then(loadCommitList);

