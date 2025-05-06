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
    div.innerHTML = `
      <strong>${c.commit_id}</strong><br>
      ${c.prompt}<br>
      ${c.timestamp}<br>
      <button class="rollback-btn" data-commit-id="${c.commit_id}">🔙 롤백</button>
    `;
    list.appendChild(div);
  });
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
fetchCommitHistory();

