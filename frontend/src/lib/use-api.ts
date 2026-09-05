"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  /** Verinin en son ne zaman tazelendiği — canlı yoklama açıkken arayüz "bu sayfa güncel mi"
   * sorusunu cevaplayabilsin diye. Yoklama kapalıysa da ilk yüklemede doluyor. */
  updatedAt: Date | null;
  reload: () => void;
}

interface InternalState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  updatedAt: Date | null;
}

interface Options {
  /** Verilirse bu aralıkla (ms) sessiz tazeleme yapılır. Bkz. aşağıdaki not. */
  pollMs?: number;
}

function toError(err: unknown): Error {
  return err instanceof Error ? err : new Error(String(err));
}

/** Küçük, bağımlılıksız bir data-fetch hook'u — bu kişisel araç için React Query gibi bir
 * kütüphaneye gerek yok (YAGNI), sadece loading/error/data üçlüsü. `loading` sıfırlaması
 * effect gövdesinde SENKRON değil, promise zincirinin ilk adımında yapılıyor — React'ın
 * "effect içinde senkron setState" uyarısını (cascading render riski) tetiklemesin diye.
 *
 * **Canlı yoklama (`pollMs`).** Faz 12 sonrası gerçek kullanımda bulundu: zamanlanmış tarama
 * arka planda Inbox'a öğe düşürüyor ama açık duran sayfa bunu göstermiyordu — kullanıcının
 * yeni bildirimi görmek için sayfayı elle yenilemesi gerekiyordu. Otomatik toplamanın tek
 * amacı "sen bakmadan da haberin olsun"ken, arayüzün bakılmasını beklemesi bu amacı boşa
 * çıkarıyordu.
 *
 * İki tasarım detayı bilinçli:
 * 1. **Tazeleme SESSİZ** — `loading` kıpırdamıyor. Aksi halde her turda iskelet ekranı
 *    yanıp sönerdi ve okurken içerik altından kayardı.
 * 2. **Sekme görünmezken yoklama durur**, görünür olunca hemen bir kez tazeler. Bu araç
 *    günlerce açık bırakılıyor (zamanlanmış tarama zaten bunu gerektiriyor); arka planda
 *    sonsuza kadar istek atmanın kimseye faydası yok. */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList,
  options?: Options
): AsyncState<T> {
  const [state, setState] = useState<InternalState<T>>({
    data: null,
    error: null,
    loading: true,
    updatedAt: null,
  });
  const [tick, setTick] = useState(0);
  const pollMs = options?.pollMs;

  // `fetcher` her render'da yeni bir closure; ref'te tutulmazsa yoklama effect'i her
  // render'da yeniden kurulur ve zamanlayıcı hiç dolmaz.
  //
  // Yazma render sırasında değil bir effect'te yapılıyor: render'da ref'e yazmak React'ın
  // saflık kuralını çiğniyor (concurrent render'da bir render atılabilir ve ref yine de
  // değişmiş kalır). Bu effect BİLEREK ilk sırada duruyor — effect'ler bildirim
  // sırasıyla çalıştığı için, aşağıdaki veri çekme ve yoklama effect'leri ref'i
  // güncellenmiş hâliyle görür. İlk render'da `useRef(fetcher)` zaten doğru değeri
  // taşıdığı için bir tur gecikme oluşmuyor.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let active = true;
    Promise.resolve()
      .then(() => {
        if (active) setState((prev) => ({ ...prev, loading: true, error: null }));
        return fetcherRef.current();
      })
      .then((result) => {
        if (active) setState({ data: result, error: null, loading: false, updatedAt: new Date() });
      })
      .catch((err) => {
        if (active) setState({ data: null, error: toError(err), loading: false, updatedAt: null });
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  useEffect(() => {
    if (!pollMs) return;
    let active = true;

    const refreshSilently = () => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      fetcherRef
        .current()
        .then((result) => {
          // Sessiz tazeleme başarısız olursa EKRANDAKİ veriyi silmiyoruz: geçici bir ağ
          // hatası yüzünden dolu bir Inbox'ın "bir şeyler ters gitti"ye dönmesi, elle
          // yenilemekten daha kötü olurdu. Hata yalnızca bir sonraki açık tazelemede görünür.
          if (active) setState((prev) => ({ ...prev, data: result, error: null, updatedAt: new Date() }));
        })
        .catch(() => {});
    };

    const onVisible = () => {
      if (document.visibilityState === "visible") refreshSilently();
    };

    const timer = window.setInterval(refreshSilently, pollMs);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      active = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, pollMs]);

  return { ...state, reload };
}
