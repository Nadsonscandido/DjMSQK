import discord
from discord.ext import commands
import yt_dlp
import asyncio

# --- Configuração Inicial ---

# 1. Dando ao bot as "permissões" (Intents) para ele ler mensagens e entrar em canais de voz
intents = discord.Intents.default()
intents.message_content = True  # Permissão para ler o conteúdo das mensagens (ex: !play <musica>)
intents.voice_states = True   # Permissão para saber quem está em qual canal de voz

# 2. Definindo o prefixo dos comandos (ex: !play) e o nome do nosso bot
bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)
bot.clent_name = "DjMSQK"

# 3. Dicionário para guardar as filas de música de cada servidor
# A "chave" é o ID do servidor, o "valor" é a lista de músicas
server_queues = {}

# 4. Dicionário para guardar o canal de texto onde o comando foi dado
text_channels = {}

# 5. Opções para o Youtube Downloader (yt-dlp)
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # Para evitar problemas de IP (ipv6)
}

# 6. Opções para o FFmpeg (o "tradutor" de áudio)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# --- Funções Ajudantes (A Lógica do DJ) ---

# Função para buscar a música no YouTube
def search_yt(search_query):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            # Tenta buscar por "ytsearch:<query>"
            info = ydl.extract_info(f"ytsearch:{search_query}", download=False)['entries'][0]
        except Exception:
            return False
    
    # Retorna a URL do áudio e o título
    return {'source': info['url'], 'title': info['title']}

# Função principal que toca a próxima música da fila
def play_next_song(ctx):
    guild_id = ctx.guild.id
    
    # Verifica se há músicas na fila daquele servidor
    if guild_id in server_queues and server_queues[guild_id]:
        
        # 1. Pega a próxima música da fila (e remove ela da lista)
        song = server_queues[guild_id].pop(0)
        
        # 2. Prepara o áudio para o Discord
        source = discord.FFmpegPCMAudio(song['source'], **FFMPEG_OPTIONS)
        
        # 3. Toca o áudio
        ctx.voice_client.play(source, after=lambda _: play_next_song(ctx))
        
        # 4. Envia a mensagem "Tocando agora:" no canal de texto certo
        # (Usamos 'asyncio' porque esta função não é 'async')
        text_channel = text_channels.get(guild_id)
        if text_channel:
            asyncio.run_coroutine_threadsafe(
                text_channel.send(f'**{bot.client_name} tocando agora:** 🎶 {song["title"]}'),
                bot.loop
            )
    else:
        # Fila vazia, pode adicionar uma lógica para sair do canal após um tempo
        pass

# --- Eventos do Bot (O que ele faz sozinho) ---

@bot.event
async def on_ready():
    print(f'Login feito como: {bot.user}')
    print(f'DjMSQK está pronto para a festa!')
    await bot.change_presence(activity=discord.Game(name="Música! Digite !play"))

# --- Comandos (O que ele faz quando você pede) ---

@bot.command(name='play', aliases=['p', 'tocar'])
async def play(ctx, *, search: str):
    """Toca uma música do YouTube ou a adiciona na fila."""
    
    # 1. Verifica se o usuário está em um canal de voz
    if not ctx.author.voice:
        await ctx.send("Você não está em um canal de voz! 😠")
        return
        
    voice_channel = ctx.author.voice.channel
    voice_client = ctx.voice_client # O bot no canal de voz
    
    # 2. Conecta o bot ao canal de voz se ele não estiver
    if not voice_client:
        await voice_channel.connect()
        voice_client = ctx.voice_client # Atualiza a referência
    
    # 3. Guarda o canal de texto para enviar as mensagens de "Tocando agora"
    guild_id = ctx.guild.id
    text_channels[guild_id] = ctx.channel

    # 4. Busca a música
    await ctx.send(f'🔎 Procurando por "{search}"... ⏳')
    song = search_yt(search)
    
    if not song:
        await ctx.send("Não consegui encontrar essa música. Tente outro nome.")
        return

    # 5. Adiciona a música na fila do servidor
    if guild_id not in server_queues:
        server_queues[guild_id] = []
        
    server_queues[guild_id].append(song)
    await ctx.send(f'**Adicionado à fila:** 👍 {song["title"]}')

    # 6. Se o bot não estiver tocando nada, ele começa a tocar
    if not voice_client.is_playing():
        play_next_song(ctx)

@bot.command(name='skip', aliases=['s', 'avançar', 'proxima'])
async def skip(ctx):
    """Pula para a próxima música da fila."""
    voice_client = ctx.voice_client
    
    if voice_client and voice_client.is_playing():
        # O .stop() ativa o 'after' da função play(), que chama play_next_song()
        voice_client.stop()
        await ctx.send("Música pulada! ⏭️")
    else:
        await ctx.send("Não estou tocando nada no momento.")

@bot.command(name='queue', aliases=['q', 'fila', 'lista'])
async def queue(ctx):
    """Mostra a fila de músicas."""
    guild_id = ctx.guild.id
    
    if guild_id in server_queues and server_queues[guild_id]:
        message = "📜 **Fila de Músicas:**\n"
        
        # Lista as próximas 10 músicas
        for i, song in enumerate(server_queues[guild_id][:10]):
            message += f"{i+1}. {song['title']}\n"
            
        if len(server_queues[guild_id]) > 10:
            message += f"...e mais {len(server_queues[guild_id]) - 10} músicas."
            
        await ctx.send(message)
    else:
        await ctx.send("A fila está vazia! 텅")

@bot.command(name='pause', aliases=['pausar'])
async def pause(ctx):
    """Pausa a música que está tocando."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Música pausada. ⏸️")

@bot.command(name='resume', aliases=['r', 'continuar'])
async def resume(ctx):
    """Continua a música que estava pausada."""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Continuando a música! ▶️")

@bot.command(name='stop', aliases=['parar', 'leave', 'sair'])
async def stop(ctx):
    """Para de tocar, limpa a fila e sai do canal."""
    guild_id = ctx.guild.id
    
    # Limpa a fila
    if guild_id in server_queues:
        server_queues[guild_id] = []
        
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await ctx.send("Até mais! 👋")


# --- Iniciar o Bot ---
# Cole seu TOKEN SECRETO aqui
TOKEN ='token' 
bot.run(TOKEN)