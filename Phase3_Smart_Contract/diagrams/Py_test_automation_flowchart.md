graph TD
    A[شروع اسکریپت اتوماسیون تست] --> B{بررسی پیش‌نیازهای محیطی};
    B -- موفق --> C[تغییر مسیر به دایرکتوری پروژه];
    B -- ناموفق --> BA[خروج از اسکریپت];
    C --> D{فعال‌سازی محیط مجازی پایتون (اختیاری)};
    D --> E[پاکسازی اجرای قبلی Hardhat Node];
    E --> F[حذف فایل‌های آدرس قدیمی قراردادها];
    F --> G{بارگذاری متغیرهای محیطی از .env};
    G -- موفق --> H[بررسی وجود متغیرهای محیطی ضروری];
    G -- ناموفق --> GA[خروج از اسکریپت];
    H -- موفق --> I[راه‌اندازی Hardhat Node با Fork از Mainnet];
    H -- ناموفق --> HA[خروج از اسکریپت];
    I --> J{بررسی آمادگی Hardhat Node (RPC)};
    J -- موفق --> K[صادرات متغیر MAINNET_FORK_RPC_URL];
    J -- ناموفق --> JA[خروج از اسکریپت];
    K --> L{اجرای اسکریپت تامین مالی حساب Deployer};
    L -- موفق --> M[دیپلوی قرارداد PredictiveManager];
    L -- ناموفق --> LA[خروج از اسکریپت];
    M -- موفق --> N[دیپلوی قرارداد BaselineMinimal];
    M -- ناموفق --> MA[خروج از اسکریپت];
    N -- موفق --> O[شروع تست‌های پایتون];
    N -- ناموفق --> NA[خروج از اسکریپت];
    O --> P{اجرای تست استراتژی Predictive};
    P --> Q[ذخیره نتیجه تست Predictive];
    Q --> R{اجرای تست استراتژی Baseline};
    R --> S[ذخیره نتیجه تست Baseline];
    S --> T[پایان تست‌های پایتون];
    T --> U[توقف Hardhat Node];
    U --> V{غیرفعال‌سازی محیط مجازی پایتون (اختیاری)};
    V --> W[نمایش نتایج نهایی تست‌ها];
    W --> X[پایان اسکریپت با کد خروجی مناسب];

    subgraph "مراحل اصلی اسکریپت"
        direction LR
        A
        B
        C
        D
        E
        F
        G
        H
        I
        J
        K
        L
        M
        N
        O
        T
        U
        V
        W
        X
    end

    subgraph "تست‌های پایتون"
        direction TB
        P
        Q
        R
        S
    end

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style X fill:#f9f,stroke:#333,stroke-width:2px
    style BA fill:#ffcccb,stroke:#333,stroke-width:2px
    style GA fill:#ffcccb,stroke:#333,stroke-width:2px
    style HA fill:#ffcccb,stroke:#333,stroke-width:2px
    style JA fill:#ffcccb,stroke:#333,stroke-width:2px
    style LA fill:#ffcccb,stroke:#333,stroke-width:2px
    style MA fill:#ffcccb,stroke:#333,stroke-width:2px
    style NA fill:#ffcccb,stroke:#333,stroke-width:2px