document.addEventListener('DOMContentLoaded', () => {
    const operationSelect = document.getElementById('operationSelect');
    const messageField = document.getElementById('messageField');
    const form = document.querySelector('form'); 
    const imageUpload = document.getElementById('imageUpload');
    const imagePreview = document.getElementById('imagePreview');
    const imagePreviewContainer = document.getElementById('imagePreviewContainer');
    const customFileLabel = document.querySelector('.custom-file-label'); 

    operationSelect.addEventListener('change', (e) => {
        messageField.style.display = e.target.value === 'encrypt' ? 'block' : 'none';
    });

    messageField.style.display = operationSelect.value === 'encrypt' ? 'block' : 'none';

    imageUpload.addEventListener('change', function (e) {
        const file = e.target.files[0];
        customFileLabel.textContent = file.name; 

        const reader = new FileReader();

        reader.onload = function (e) {
            imagePreview.src = e.target.result;
            imagePreviewContainer.style.display = 'block'; 
        }

        if (file) {
            reader.readAsDataURL(file);
        } else {
            imagePreview.src = "#"; 
            imagePreviewContainer.style.display = 'none';
        }
    });

    
    form.addEventListener('submit', function (e) {
        setTimeout(() => {
            form.reset();
            customFileLabel.textContent = 'Choose file'; 
            imagePreview.src = "#";  
            imagePreviewContainer.style.display = 'none'; 
        }, 1000); 
    });
});
