from django.db import models

class Prime(models.Model):
    ativo = models.BooleanField(default=True)
    criacao = models.DateTimeField(auto_now_add=True, null=True)
    atualizado = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class Jogo(Prime):
    nome_jogo = models.CharField(max_length=200)
    imagem_jogo = models.ImageField(upload_to='imagem_jogo/')
    arquivo_jogo = models.FileField(upload_to='jogo/')

    class Meta:
        verbose_name = 'Jogo'
        verbose_name_plural = 'Jogos'

    def __str__(self):
        return self.nome_jogo


class BuildJogos(models.Model):
    descricao_build = models.CharField(max_length=200)
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE)
    arquivo_build = models.FileField(upload_to='arquivo_build/')

    class Meta:
        verbose_name = 'Build Jogo'
        verbose_name_plural = 'Build Jogos'

    def __str__(self):
        return self.descricao_build

