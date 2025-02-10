document.addEventListener('DOMContentLoaded', function() {
    // Обработка подтверждения удаления
    const deleteForms = document.querySelectorAll('.delete-group-form');
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!confirm('Вы уверены, что хотите удалить группу? Это действие нельзя отменить.')) {
                e.preventDefault();
            }
        });
    });
});
