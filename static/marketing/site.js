(() => {
  const video = document.querySelector('#intro-video');
  const play = document.querySelector('.film-play');
  if (video && play) {
    play.hidden = false;
    play.addEventListener('click', async () => {
      try {
        await video.play();
        video.focus();
      } catch {
        play.hidden = true;
        video.focus();
      }
    });
    video.addEventListener('play', () => { play.hidden = true; });
    video.addEventListener('ended', () => { play.hidden = false; });
  }
  const form = document.querySelector('.contact-panel form');
  if (form) {
    const update = () => {
      const demo = form.querySelector('input[name="type"]:checked')?.value === 'demo';
      form.querySelector('.demo-fields').hidden = !demo;
      form.querySelectorAll('.demo-fields input').forEach(input => { input.disabled = !demo; });
      form.querySelector('#id_shop_name').required = demo;
      form.querySelector('#id_message').required = !demo;
    };
    form.querySelectorAll('input[name="type"]').forEach(input => input.addEventListener('change', update));
    update();
    document.querySelector('.error-summary')?.focus();
  }
})();
