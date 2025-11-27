# Payments

**Payments** adalah package Python modular dan fleksibel untuk integrasi berbagai **payment gateway**.  
Dirancang untuk memudahkan developer dalam membuat transaksi, mengecek status, dan menangani webhook dari gateway berbeda tanpa mengubah kode utama.

**Fitur Utama:**
- Multi-Gateway Ready: Midtrans & Flip, mudah ditambah gateway lain.
- Async & FastAPI Friendly: Semua fungsi async, siap dipakai di project async.
- Modular Structure: Gateway dan webhook dipisah untuk kemudahan maintain dan scale.
- Logging & Error Handling: Transaksi dan webhook tercatat, error mudah dilacak.
- Callback & Custom Logic: Bisa inject callback untuk status transaksi tertentu.
- DRY & Reusable: Base class/interface untuk semua gateway agar konsisten.


