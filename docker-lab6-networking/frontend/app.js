'use strict';
const api = '/api';
const statusElement = document.querySelector('#status');

async function request(path, options = {}) {
  const response = await fetch(api + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Ошибка запроса');
  return data;
}

async function loadCart() {
  const cart = await request('/cart');
  document.querySelector('#cart-count').textContent = cart.count;
  document.querySelector('#cart-total').textContent = '$' + cart.total;
  document.querySelector('#empty-cart').hidden = cart.count !== 0;
  const list = document.querySelector('#cart-items');
  list.replaceChildren();
  for (const item of cart.items) {
    const li = document.createElement('li');
    const name = document.createElement('span');
    const price = document.createElement('strong');
    name.textContent = item.name;
    price.textContent = '$' + item.price;
    li.append(name, price);
    list.append(li);
  }
}

async function addProduct(id, button) {
  button.disabled = true;
  try {
    await request('/cart/add/' + id, {method: 'POST'});
    await loadCart();
    statusElement.textContent = 'Товар добавлен в корзину';
  } catch (error) {
    statusElement.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function main() {
  try {
    const products = await request('/products');
    const symbols = ['◈', '◉', '▤'];
    const container = document.querySelector('#products');
    for (const [index, product] of products.entries()) {
      const card = document.createElement('article');
      const art = document.createElement('div');
      art.className = 'product-art art-' + index;
      art.setAttribute('aria-hidden', 'true');
      art.textContent = symbols[index] || '◈';
      const heading = document.createElement('h3');
      heading.textContent = product.name;
      const price = document.createElement('p');
      price.className = 'price';
      price.textContent = '$' + product.price;
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Добавить в корзину';
      button.addEventListener('click', () => addProduct(product.id, button));
      card.append(art, heading, price, button);
      container.append(card);
    }
    await loadCart();
    statusElement.textContent = 'Магазин готов';
  } catch (error) {
    statusElement.textContent = 'Не удалось загрузить магазин: ' + error.message;
  }
}

document.querySelector('#clear-cart').addEventListener('click', async () => {
  try {
    await request('/cart', {method: 'DELETE'});
    await loadCart();
    statusElement.textContent = 'Корзина очищена';
  } catch (error) {
    statusElement.textContent = error.message;
  }
});
main();
