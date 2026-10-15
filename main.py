import os
import time
import random
import logging
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://sede.administracionespublicas.gob.es/pagina/index/directorio/icpplus/"

TOKEN = os.getenv("TELEGRAM_TOKEN", "8975628897:AAEsWs_b3hmGCXZzqh513pV7-t-DabJg9zQ")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6008287114")

PROVINCIA_SELECCIONADA = "Toledo"
TRAMITE_OBJETIVO = "toma de huellas"

NIE = "Y9054113Q"
NOMBRE = "OUSSAMA SAIDI"
ANIO = "2007"
NACIONALIDAD = "MARRUECOS"

SIN_CITAS = "en este momento no hay citas disponibles"
BLOQUEO = "the requested url was rejected"
DEMASIADAS_PETICIONES = "too many requests"
CADUCADO = "su sesión ha caducado"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def enviar_telegram(mensaje):
    try:
        respuesta = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"},
            timeout=15,
        )
        respuesta.raise_for_status()
        return respuesta.json().get("ok") is True
    except requests.RequestException as error:
        logging.error("Error de Telegram: %s", error)
        return False

def leer_texto(page):
    try:
        return " ".join(page.locator("body").inner_text().split()).casefold()
    except PlaywrightTimeoutError:
        return ""

def comprobar_estado_temprano(page):
    texto = leer_texto(page)
    if DEMASIADAS_PETICIONES in texto or "429" in texto:
        logging.warning("⚠️ Servidor saturado (Error 429).")
        return "429"
    if "the requested url was rejected" in texto and "icpplus" not in texto:
        logging.warning("⚠️ Cortafuegos detectado.")
        return "bloqueo"
    if CADUCADO in texto:
        logging.warning("⚠️ Sesión caducada.")
        return "caducado"
    return "ok"

def pulsar_acceso(page):
    boton = page.get_by_text("Acceder al Procedimiento", exact=False).first
    boton.wait_for(state="visible", timeout=20000)
    time.sleep(random.uniform(1.0, 2.0))
    boton.click()

def seleccionar_tramite(page):
    objetivo = TRAMITE_OBJETIVO.casefold()
    time.sleep(random.uniform(1.5, 2.5))
    for i in range(page.locator("select").count()):
        menu = page.locator("select").nth(i)
        try:
            opciones = menu.locator("option")
            for j in range(opciones.count()):
                opcion = opciones.nth(j)
                etiqueta = " ".join(opcion.inner_text().split())
                normalizada = etiqueta.casefold()
                if objetivo in normalizada:
                    valor = opcion.get_attribute("value")
                    if valor:
                        menu.select_option(value=valor)
                        logging.info("Trámite seleccionado: %s", etiqueta)
                        return True
        except Exception:
            continue
    return False

def aceptar(page):
    selectores = [
        "button:has-text('Aceptar')",
        "input[value='Aceptar']",
        "input#btnAceptar",
        "input#btnEnviar",
        "text=Aceptar"
    ]
    for selector in selectores:
        try:
            boton = page.locator(selector).first
            if boton.is_visible(timeout=2000):
                boton.scroll_into_view_if_needed()
                time.sleep(random.uniform(1.0, 1.8))
                boton.click(force=True)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                logging.info("Botón Aceptar pulsado.")
                return True
        except Exception:
            continue
    return False

def rellenar_formulario_datos(page):
    logging.info("Rellenando formulario de datos personales...")
    page.wait_for_selector("input[type='text'], input#txtIdCit", timeout=15000)
    time.sleep(1.5)

    try:
        radio_nie = page.locator("input[type='radio'][value='NIE'], input#rdbTipoDocNie").first
        if radio_nie.is_visible(timeout=2000):
            radio_nie.check()
    except Exception:
        pass

    # NIE
    input_nie = page.locator("input#txtIdCit, input[name*='IdCit'], input[name*='Citado']").first
    if not input_nie.is_visible():
        input_nie = page.locator("input[type='text']").nth(0)
    input_nie.click()
    input_nie.fill("")
    input_nie.type(NIE, delay=random.randint(90, 150))
    logging.info("NIE introducido: %s", NIE)

    # Nombre
    input_nombre = page.locator("input#txtNombSoli, input[name*='Nomb']").first
    if not input_nombre.is_visible():
        input_nombre = page.locator("input[type='text']").nth(1)
    input_nombre.click()
    input_nombre.fill("")
    input_nombre.type(NOMBRE, delay=random.randint(90, 150))
    logging.info("Nombre introducido: %s", NOMBRE)

    # Nacionalidad
    try:
        select_pais = page.locator("select#txtPaisNac, select[name*='Pais']").first
        if select_pais.is_visible(timeout=2000):
            try:
                select_pais.select_option(label=NACIONALIDAD)
            except Exception:
                opciones = select_pais.locator("option")
                for i in range(opciones.count()):
                    if NACIONALIDAD in opciones.nth(i).inner_text().upper():
                        val = opciones.nth(i).get_attribute("value")
                        select_pais.select_option(value=val)
                        break
            logging.info("Nacionalidad seleccionada: %s", NACIONALIDAD)
    except Exception as e:
        logging.warning("Aviso al seleccionar país: %s", e)

    time.sleep(1.5)
    aceptar(page)

def evaluar_resultado_final(page):
    time.sleep(3)
    texto = leer_texto(page)
    url_actual = page.url

    if DEMASIADAS_PETICIONES in texto or "429" in texto:
        return "429"
    if "the requested url was rejected" in texto and "icpplus" not in texto:
        return "bloqueo"
    if CADUCADO in texto:
        return "caducado"
    
    if SIN_CITAS in texto or "en este momento no hay citas" in texto:
        logging.info("ℹ️ [SIN CITAS] No hay huecos libres.")
        mensaje_sin_citas = (
            f"❌ *Mala noticia: No hay citas*\n\n"
            f"📍 *Provincia:* {PROVINCIA_SELECCIONADA}\n"
            f"👤 *Solicitante:* {NOMBRE}\n"
            f"🆔 *NIE:* {NIE}\n\n"
            "En este momento no hay citas disponibles. Lo intentaré de nuevo en 6 minutos."
        )
        enviar_telegram(mensaje_sin_citas)
        return "sin_citas"

    if "cl@ve" in texto and "disposición" in texto:
        logging.info("💡 Citas reservadas exclusivamente para Cl@ve.")
        return "sin_citas"

    # ¡HAY CITAS REALES DISPONIBLES!
    logging.warning("🚨 ¡¡¡HAY CITAS DISPONIBLES EN TOLEDO!!! 🚨")
    mensaje = (
        f"🔥 *¡EMERGENCIA: CITAS DISPONIBLES EN {PROVINCIA_SELECCIONADA.upper()}!* 🔥\n\n"
        f"👤 *Solicitante:* {NOMBRE}\n"
        f"🆔 *NIE:* {NIE}\n\n"
        "✅ ¡Se han abierto huecos! Entra rápido a reservar.\n"
        f"🔗 [ACCEDER A LA SEDE]({url_actual})"
    )
    enviar_telegram(mensaje)
    return "citas_encontradas"

def ejecutar_ciclo(page):
    logging.info("Abriendo sede...")
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    if comprobar_estado_temprano(page) in ("429", "bloqueo"):
        return "429"

    pulsar_acceso(page)
    if comprobar_estado_temprano(page) in ("429", "bloqueo"):
        return "429"

    time.sleep(random.uniform(1.0, 2.0))
    provincia = page.locator("select#form, select[name='form']").first
    provincia.wait_for(state="visible", timeout=15000)
    provincia.select_option(label=PROVINCIA_SELECCIONADA)

    if not aceptar(page):
        logging.error("No se encontró el botón Aceptar de provincia.")
        return "desconocido"

    if comprobar_estado_temprano(page) in ("429", "bloqueo"):
        return "429"

    if not seleccionar_tramite(page):
        logging.warning("No se encontró la opción del trámite.")
        return "desconocido"

    if not aceptar(page):
        logging.warning("No se encontró el botón Aceptar del trámite.")
        return "desconocido"

    if comprobar_estado_temprano(page) in ("429", "bloqueo"):
        return "429"

    logging.info("Avanzando pantalla de avisos...")
    time.sleep(1.5)
    try:
        btn_entrar = page.locator("input#btnEntrar, input[value='Entrar'], button#btnEntrar").first
        if btn_entrar.is_visible(timeout=3000):
            btn_entrar.click(force=True)
        else:
            btn_sin_clave = page.locator("text=Presentación sin Cl@ve").first
            btn_sin_clave.click(force=True)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception as e:
        logging.warning("Error al pasar avisos: %s", e)

    if comprobar_estado_temprano(page) in ("429", "bloqueo"):
        return "429"

    try:
        rellenar_formulario_datos(page)
    except Exception as e:
        logging.warning("Error introduciendo datos: %s", e)

    if comprobar_estado_temprano(page) in ("429", "bloqueo"):
        return "429"

    logging.info("Pulsando 'Solicitar Cita'...")
    try:
        time.sleep(1.5)
        btn_solicitar = page.locator("input[value='Solicitar Cita'], button:has-text('Solicitar Cita'), input#btnEnviar").first
        if btn_solicitar.is_visible(timeout=5000):
            btn_solicitar.click(force=True)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception as e:
        logging.warning("Aviso en Solicitar Cita: %s", e)

    return evaluar_resultado_final(page)

def main():
    with sync_playwright() as p:
        # En la nube headless debe ser True obligatoriamente
        navegador = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )

        try:
            while True:
                ancho = random.choice([1280, 1366, 1440, 1920])
                alto = random.choice([768, 800, 900, 1080])
                
                contexto = navegador.new_context(
                    viewport={"width": ancho, "height": alto},
                    locale="es-ES",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                page = contexto.new_page()

                try:
                    resultado = ejecutar_ciclo(page)
                except PlaywrightTimeoutError:
                    logging.warning("Tiempo de espera agotado.")
                    resultado = "desconocido"
                except Exception:
                    logging.exception("Error durante la navegación.")
                    resultado = "desconocido"
                finally:
                    contexto.close()

                if resultado in ("429", "bloqueo"):
                    espera = random.randint(480, 600)
                    logging.warning(f"🛑 Pausa anti-bloqueo: {espera // 60} minutos...")
                else:
                    espera = 360
                    logging.info(f"⏳ Siguiente intento en 6 minutos ({espera} segundos)...")

                time.sleep(espera)

        except KeyboardInterrupt:
            logging.info("Monitor detenido.")
        finally:
            navegador.close()

if __name__ == "__main__":
    main()
