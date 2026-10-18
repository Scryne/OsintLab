"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  /** Gösterilecek veri HENÜZ yok (ilk yükleme ya da bağımlılık değişti). Sayfalar iskeleti
   * yalnızca buna bakarak gösterir. */
  loading: boolean;
  /** Elde veri varken arka planda tazeleniyor (`reload()` ya da yoklama). Ekran yerinde kalır. */
  refreshing: boolean;
  /** Verinin en son ne zaman tazelendiği — canlı yoklama açıkken arayüz "bu sayfa güncel mi"
   * sorusunu cevaplayabilsin diye. Yoklama kapalıysa da ilk yüklemede doluyor. */
  updatedAt: Date | null;
  reload: () => void;
}

interface InternalState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refreshing: boolean;
  updatedAt: Date | null;
}

interface Options {
  /** Verilirse bu aralıkla (ms) sessiz tazeleme yapılır. Bkz. aşağıdaki not. */
  pollMs?: number;
}

function toError(err: unknown): Error {
  return err instanceof Error ? err : new Error(String(err));
}

function sameDeps(a: React.DependencyList | null, b: React.DependencyList): boolean {
  return a !== null && a.length === b.length && a.every((value, i) => Object.is(value, b[i]));
}

/** Küçük, bağımlılıksız bir data-fetch hook'u — bu kişisel araç için React Query gibi bir
 * kütüphaneye gerek yok (YAGNI), sadece loading/error/data üçlüsü. `loading` sıfırlaması
 * effect gövdesinde SENKRON değil, promise zincirinin ilk adımında yapılıyor — React'ın
 * "effect içinde senkron setState" uyarısını (cascading render riski) tetiklemesin diye.
 *
 * **`reload()` ekranı yıkmaz (2026-10-18 denetimi).** Eskiden her `reload()` `loading`'i true
 * yapıyordu ve sayfalar bu sırada içeriği iskeletle değiştiriyordu: Investigation'da yazılmakta
 * olan Analysis metni (editörün yerel durumu) bir durum geçişinden sonra kayboluyor, entity
 * sayfası Claims sekmesinden Timeline'a atılıyor, 200 satırlık kuyrukta her promote kaydırma
 * konumunu sıfırlıyor, promote sonuç paneli ise hiç görünmüyordu (satır yeniden kuruluyordu).
 * Artık elde veri varken tazeleme `refreshing` ile işaretleniyor ve ekran yerinde kalıyor;
 * `loading` yalnızca gösterilecek veri yokken (ilk yükleme, başka bir kayda geçiş) true.
 *
 * **Yarışlar.** Her isteğe artan bir sıra numarası veriliyor; daha eski bir istek daha yeni
 * bir sonucun üzerine yazamıyor (mutasyondan önce başlamış bir yoklama, mutasyon sonrası
 * tazelemeden sonra dönerse bayat veriyi geri getiriyordu).
 *
 * **Canlı yoklama (`pollMs`).** Faz 12 sonrası gerçek kullanımda bulundu: zamanlanmış tarama
 * arka planda Inbox'a öğe düşürüyor ama açık duran sayfa bunu göstermiyordu. İki detay
 * bilinçli: tazeleme SESSİZ (iskelet yanıp sönmez) ve sekme görünmezken yoklama durur. Önceki
 * istek hâlâ sürüyorsa yeni tur ATLANIR: yavaş bir uç (kuyruk bir dönem 5 dakika sürüyordu)
 * her turda yeni bir istek ekleyip backend'i boğuyordu. */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList,
  options?: Options
): AsyncState<T> {
  const [state, setState] = useState<InternalState<T>>({
    data: null,
    error: null,
    loading: true,
    refreshing: false,
    updatedAt: null,
  });
  const [tick, setTick] = useState(0);
  const pollMs = options?.pollMs;

  // `fetcher` her render'da yeni bir closure; ref'te tutulmazsa yoklama effect'i her
  // render'da yeniden kurulur ve zamanlayıcı hiç dolmaz. Yazma render sırasında değil bir
  // effect'te — render'da ref'e yazmak React'ın saflık kuralını çiğniyor. Bu effect BİLEREK
  // ilk sırada: effect'ler bildirim sırasıyla çalıştığı için aşağıdakiler güncel ref'i görür.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const seqRef = useRef(0);
  const appliedRef = useRef(0);
  const inFlightRef = useRef(0);
  const lastDepsRef = useRef<React.DependencyList | null>(null);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let active = true;
    // Aynı bağımlılıklarla yeniden çalışıyorsak bu bir tazeleme (reload); değilse yeni veri.
    const isRefresh = sameDeps(lastDepsRef.current, deps);
    lastDepsRef.current = deps;
    const seq = ++seqRef.current;
    inFlightRef.current += 1;
    Promise.resolve()
      .then(() => {
        if (active) {
          setState((prev) =>
            isRefresh && prev.data !== null
              ? { ...prev, refreshing: true }
              : { ...prev, loading: true, error: null }
          );
        }
        return fetcherRef.current();
      })
      .then((result) => {
        if (!active || seq < appliedRef.current) return;
        appliedRef.current = seq;
        setState({ data: result, error: null, loading: false, refreshing: false, updatedAt: new Date() });
      })
      .catch((err) => {
        if (!active || seq < appliedRef.current) return;
        appliedRef.current = seq;
        // Tazeleme başarısızsa eldeki veri silinmez; hata yine de gösterilir.
        setState((prev) => ({
          data: isRefresh ? prev.data : null,
          error: toError(err),
          loading: false,
          refreshing: false,
          updatedAt: isRefresh ? prev.updatedAt : null,
        }));
      })
      .finally(() => {
        inFlightRef.current -= 1;
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
      if (inFlightRef.current > 0) return;
      const seq = ++seqRef.current;
      inFlightRef.current += 1;
      fetcherRef
        .current()
        .then((result) => {
          // Sessiz tazeleme başarısız olursa EKRANDAKİ veriyi silmiyoruz: geçici bir ağ
          // hatası yüzünden dolu bir Inbox'ın "bir şeyler ters gitti"ye dönmesi, elle
          // yenilemekten daha kötü olurdu. Hata yalnızca bir sonraki açık tazelemede görünür.
          if (!active || seq < appliedRef.current) return;
          appliedRef.current = seq;
          setState((prev) => ({ ...prev, data: result, error: null, updatedAt: new Date() }));
        })
        .catch(() => {})
        .finally(() => {
          inFlightRef.current -= 1;
        });
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
